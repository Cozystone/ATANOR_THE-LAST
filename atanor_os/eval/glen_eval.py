"""Evaluator for the glen, one of the island's five places: isle_eval with this place's name.
Usage: python -m atanor_os.eval.glen_eval <course_dir> <eval_seed> <out.json>
       python -m atanor_os.eval.glen_eval oracle <course_dir> <eval_seed>
"""
import sys

from . import isle_eval

BODY = 'glen'


def world(root, eval_seed, drift, ticks=0):
    return isle_eval.world(BODY, root, eval_seed, drift, ticks)


def evaluate(course, eval_seed, out_file):
    return isle_eval.evaluate(BODY, course, eval_seed, out_file)


def oracle_only(course, eval_seed):
    return isle_eval.oracle_only(BODY, course, eval_seed)


if __name__ == '__main__':
    isle_eval.main(BODY, sys.argv)
