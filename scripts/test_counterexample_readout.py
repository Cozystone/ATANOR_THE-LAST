from scripts.counterexample_adaptation_eval import COUNTS, classify, stable_acquisition


def rows(pattern):
    return [dict(count=c,arm='fresh',life=i,changed_exact=j<pattern[c])
            for c in COUNTS for i in range(4) for j in range(4)]


def test_stability_requires_later_counts_not_first_crossing():
    assert stable_acquisition(rows({0:0,1:4,2:1,4:4,8:4}),'fresh')==4
    assert stable_acquisition(rows({0:0,1:0,2:0,4:0,8:3}),'fresh')==8


def test_censoring_is_not_equality():
    assert stable_acquisition(rows({c:0 for c in COUNTS}),'fresh') is None
    assert classify(None,None)=='UNRESOLVED_WITHIN_8'
    assert classify(None,4)=='EXPERIENCED_FASTER_WITHIN_BUDGET'
    assert classify(2,None)=='EXPERIENCED_SLOWER_WITHIN_BUDGET'
    assert classify(4,4)=='SAME_OBSERVED_THRESHOLD_NOT_EQUIVALENCE'
