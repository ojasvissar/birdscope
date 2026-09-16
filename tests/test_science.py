import json
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from fieldwork.checklists import prepare_checklists, ID
from fieldwork.products import weighted_mean, summarize_weekly, summarize_trends

CONFIG = {"target_species": "Test Bird", "max_duration_minutes": 300,
          "max_distance_km": 5, "max_observers": 10, "spatial_block_degrees": .05}


def sampling(ids):
    return pd.DataFrame([{ID: i, "GROUP IDENTIFIER": None, "ALL SPECIES REPORTED": 1,
                          "PROTOCOL CODE": "P21", "DURATION MINUTES": 30,
                          "EFFORT DISTANCE KM": None, "NUMBER OBSERVERS": 1,
                          "LATITUDE": 1.3, "LONGITUDE": 103.8,
                          "OBSERVATION DATE": "2012-03-01", "TIME OBSERVATIONS STARTED": "08:00:00",
                          "LOCALITY ID": "L1"} for i in ids])


def observation(i, n="1", approved=1):
    return {ID: i, "COMMON NAME": "Test Bird", "OBSERVATION COUNT": n, "APPROVED": approved}


class ChecklistScienceTests(unittest.TestCase):
    def test_complete_denominator_and_presence_only_x(self):
        s=sampling(["seen", "unseen", "incomplete"])
        s.loc[2, "ALL SPECIES REPORTED"]=0
        frame,qc=prepare_checklists(pd.DataFrame([observation("seen", "X")]),s,CONFIG)
        self.assertEqual(frame.detected.tolist(),[1,0])
        self.assertTrue(np.isnan(frame.loc[0,"count"]))
        self.assertEqual(frame.loc[1,"count"],0)
        self.assertEqual(qc["eligible_visits"],2)

    def test_group_union_detection_and_max_not_sum(self):
        s=sampling(["A", "B", "C"]); s.loc[:1,"GROUP IDENTIFIER"]="G1"
        frame,_=prepare_checklists(pd.DataFrame([observation("A", "2"),observation("B", "3")]),s,CONFIG)
        self.assertEqual(len(frame),2)
        group=frame.loc[frame.visit_id.eq("group:G1")].iloc[0]
        self.assertEqual(group.detected,1)
        self.assertEqual(group["count"],3)

    def test_rejected_detection_is_unknown_not_absence(self):
        s=sampling(["A", "B"])
        frame,_=prepare_checklists(pd.DataFrame([observation("A",approved=0)]),s,CONFIG)
        self.assertEqual(frame[ID].tolist(),["B"])
        self.assertEqual(frame.detected.tolist(),[0])

    def test_effort_and_protocol_rejections(self):
        s=sampling(["good","incidental","long","missing_distance"])
        s.loc[1,"PROTOCOL CODE"]="P20"
        s.loc[2,"DURATION MINUTES"]=301
        s.loc[3,"PROTOCOL CODE"]="P22"
        frame,_=prepare_checklists(pd.DataFrame([observation("good")]),s,CONFIG)
        self.assertEqual(frame[ID].tolist(),["good"])
        self.assertEqual(frame.distance.tolist(),[0])

    def test_duplicate_event_ids_fail(self):
        with self.assertRaisesRegex(ValueError,"unique"):
            prepare_checklists(pd.DataFrame([observation("A")]),sampling(["A","A"]),CONFIG)

    def test_species_scope_must_be_known(self):
        with self.assertRaisesRegex(ValueError,"scope"):
            prepare_checklists(pd.DataFrame([observation("A")]),sampling(["A"]),
                               {**CONFIG,"target_species":"Wrong species"})

    def test_localities_connect_adjacent_blocks(self):
        s=sampling(["A", "B", "C"])
        s["LONGITUDE"]=[103.79,103.81,103.95]
        s["LOCALITY ID"]=["shared","shared","other"]
        frame,_=prepare_checklists(pd.DataFrame([observation("A")]),s,CONFIG)
        self.assertEqual(frame.loc[0,"block"],frame.loc[1,"block"])
        self.assertNotEqual(frame.loc[0,"block"],frame.loc[2,"block"])


class ProductScienceTests(unittest.TestCase):
    def test_zero_retained_missing_excluded(self):
        self.assertEqual(weighted_mean([0,4,np.nan],[1,3,100]),3)
        self.assertIsNone(weighted_mean([np.nan],[1]))

    def test_negative_weights_fail(self):
        with self.assertRaises(ValueError):
            weighted_mean([1,2],[-1,3])

    def test_fractional_area_weighting(self):
        weekly=pd.DataFrame({"cell_id":[1,2],"week":[1,1],"date":["2023-01-04"]*2,
                             "abundance":[1.,3.],"occurrence":[.2,.6]})
        cells=pd.DataFrame({"cell_id":[1,2],"area_km2":[3.,1.]})
        weights=cells.assign(region="north")
        out=summarize_weekly(weekly,cells,weights)
        self.assertTrue(np.allclose(out.abundance,1.5))
        self.assertTrue(np.allclose(out.occurrence,.3))
        self.assertTrue(np.allclose(out.supported_area_km2,4))

    def test_regional_interval_from_joint_replicates(self):
        # Perfectly anticorrelated cell trends cancel in EACH replicate.
        # Averaging marginal cell interval limits would incorrectly imply uncertainty.
        folds=pd.DataFrame({"srd_id":[1,2]*3,"fold":[1,1,2,2,3,3],
                            "abd":[1.]*6,"abd_ppy":[-10,10,0,0,10,-10]})
        weights=pd.DataFrame({"srd_id":[1,2],"region":["north"]*2,"area_km2":[1.,1.]})
        out,replicates=summarize_trends(folds,weights)
        self.assertTrue(np.allclose(out.lower,0))
        self.assertTrue(np.allclose(out.upper,0))
        self.assertTrue(np.allclose(replicates.annual_percent,0))

    def test_duplicate_ensemble_rows_fail(self):
        f=pd.DataFrame({"srd_id":[1,1],"fold":[1,1]})
        with self.assertRaisesRegex(ValueError,"Duplicate"):
            summarize_trends(f,pd.DataFrame())


@unittest.skipUnless(Path("dist/data/analysis.json").exists(),"Run pipeline for integration checks")
class PublishedContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads(Path("dist/data/analysis.json").read_text())

    def test_52_unique_weeks_per_region(self):
        d=pd.DataFrame(self.data["weekly_summary"])
        self.assertEqual(len(d),208)
        self.assertFalse(d.duplicated(["region","week"]).any())
        self.assertEqual(set(d.groupby("region").week.nunique()),{52})

    def test_regional_area_and_abundance_reconstruct_whole(self):
        d=pd.DataFrame(self.data["weekly_summary"])
        for week,g in d.groupby("week"):
            all_row=g[g.region.eq("all")].iloc[0]; parts=g[~g.region.eq("all")]
            self.assertAlmostEqual(parts.supported_area_km2.sum(),all_row.supported_area_km2,places=5)
            self.assertAlmostEqual(weighted_mean(parts.abundance,parts.supported_area_km2),all_row.abundance,places=6)

    def test_map_arrays_and_uncertainty_order(self):
        geo=json.loads(Path("dist/data/status.geojson").read_text())
        self.assertEqual(len(geo["features"]),self.data["metadata"]["status_cells"])
        for f in geo["features"]:
            p=f["properties"]
            self.assertEqual(len(p["abundance"]),52)
            for l,m,u in zip(p["lower"],p["abundance"],p["upper"]):
                if None not in [l,m,u]:
                    self.assertLessEqual(l,m);self.assertLessEqual(m,u)

    def test_trend_bounds_and_replicate_counts(self):
        for r in self.data["regional_trends"]:
            self.assertEqual(r["folds"],100)
            self.assertLessEqual(r["lower"],r["annual_percent"])
            self.assertLessEqual(r["annual_percent"],r["upper"])

    def test_no_private_observation_fields_published(self):
        for p in Path("dist").rglob("*"):
            if p.is_file() and p.suffix in [".csv",".geojson",".json"]:
                text=p.read_text()
                self.assertNotIn('"OBSERVER ID"',text)
                self.assertNotIn('"SAMPLING EVENT IDENTIFIER"',text)
                self.assertNotIn('"visit_id"',text)

    @unittest.skipUnless(Path("outputs/private/oof_predictions.csv").exists(),"Local OOF output required")
    def test_each_spatial_group_in_one_test_fold(self):
        d=pd.read_csv("outputs/private/oof_predictions.csv")
        self.assertTrue(d.groupby("block").fold.nunique().eq(1).all())
        self.assertFalse(d.visit_id.duplicated().any())
        self.assertEqual(len(d),self.data["checklists"]["eligible_visits"])
        for c in ["prevalence","effort","space_time"]:
            self.assertTrue(d[c].between(0,1).all())


if __name__ == "__main__":
    unittest.main()
