import argparse
import os
from pathlib import Path
from utils import mkdir_if_not_exist, read_anchor_file
import shutil


def primary_mapping(aligned_dir, output_dir):
    """
    Pick the minimal edit distance reference text for each decoded audio clip 
    and filter the results to find an actual match.
    """
    search_results = os.path.join(output_dir, "scp_map")
    dump = os.path.join(output_dir, "dump")
    hyp_res = {}
    ref_res = {}
    for fname_hash in os.listdir(aligned_dir):
        file = os.path.join(aligned_dir, fname_hash)
        fname, _, _, _, _csid = read_anchor_file(file)
        hyp, ref = Path(fname).stem.split("_vs_")
        csid = [int(item) for item in _csid]
        c = csid[0]
        # TODO: Perhaps the absolute count of C is not the best criterion
        if hyp not in hyp_res or hyp_res[hyp][1][0] < c:
            hyp_res[hyp] = (ref, csid)
        if ref not in ref_res or ref_res[ref][1][0] < c:
            ref_res[ref] = (hyp, csid)
    matched_hyp = set()
    matched_ref = set()
    all_refs = set()
    all_hyps = set()
    stats_dir = os.path.join(output_dir, "stats")
    mkdir_if_not_exist(stats_dir)
    matched_anchor_dir = os.path.join(output_dir, "anchors")
    mkdir_if_not_exist(matched_anchor_dir)
    res = set()
    with open(search_results, "w") as f:
        with open(dump, "w") as ofh:
            for ref, _ in ref_res.items():
                all_refs.add(ref)
            for hyp, info in hyp_res.items():
                ref = info[0]
                all_hyps.add(hyp)
                # Bidirectional-correspondence is considered as a valid match
                if ref_res[ref][0] == hyp:
                    matched_hyp.add(hyp)
                    matched_ref.add(ref)
                    res.add((hyp, ref))
                    print(hyp, ref, file=f)
                    print(hyp, ref, *info[1], sum(info[1]),
                          f"{(info[1][0] / sum(info[1])):.2f}", file=ofh)
    for fname_hash in os.listdir(aligned_dir):
        file = os.path.join(aligned_dir, fname_hash)
        fname, _, _, _, _csid = read_anchor_file(file)
        hyp, ref = Path(fname).stem.split("_vs_")
        if (hyp, ref) in res:
            # Copy the corresponding anchor file to the matched_anchor_dir
            shutil.copy(file, os.path.join(matched_anchor_dir, f"{hyp}_{ref}.anchor"))
    with open(os.path.join(stats_dir, "unmatched_hyp"), "w") as f:
        for hyp in all_hyps - matched_hyp:
            print(hyp, file=f)
    with open(os.path.join(stats_dir, "unmatched_ref"), "w") as f:
        for ref in all_refs - matched_ref:
            print(ref, file=f)
    with open(os.path.join(stats_dir, "searched_hyp"), "w") as f:
        for hyp in all_hyps:
            print(hyp, file=f)
    with open(os.path.join(stats_dir, "searched_ref"), "w") as f:
        for ref in all_refs:
            print(ref, file=f)


def main():
    parser = argparse.ArgumentParser(
        description='Pick and filter the best alignment results between decoded audio clips and reference text clips')
    parser.add_argument('--aligned_dir', type=Path, required=True,
                        help='The alignment files generated by the align_text script')
    parser.add_argument('--output_dir', type=Path, required=True,
                        help='The full path to the directory in which the results and dumps will be stored')
    args = parser.parse_args()

    primary_mapping(args.aligned_dir, args.output_dir)


if __name__ == "__main__":
    main()
