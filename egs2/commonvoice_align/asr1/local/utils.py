import numpy as np
from typing import (List, overload)
import json
from pathlib import Path
import re


def mkdir_if_not_exist(path):
    Path(path).mkdir(parents=True, exist_ok=True)


def segid2uttid(segid):
    splitted = segid.split("_")
    return "_".join(splitted[:-1])


def scpid2mid(scpid):
    return scpid.split("_")[-1]


def extract_mid(string):
    match = re.search(r"_(M\d+)(_)", string)
    if match:
        return match.group(1)
    return None


def read_wavscp(file, raw=False):
    """
    Read the wav.scp file and return a dict of {uttid: wav_path}.
    """
    res = {}
    with open(file, "r") as f:
        for line in f:
            if raw:
                line = line.strip().split()
                mid, wav_path = line[0], line[3]
            else:
                mid, wav_path = line.strip().split(maxsplit=1)
            res[mid] = wav_path
    return res


def read_utt2spk(file, ignore_seg=False):
    """
    Read the utt2spk file and return a dict of {uttid: spkid}.
    """
    res = {}
    with open(file, "r") as f:
        for line in f:
            uttid, spkid = line.strip().split(maxsplit=1)
            if ignore_seg:
                uttid = "_".join(uttid.split("_")[:-1])
            res[uttid] = spkid
    return res


def read_anchor_file(file, return_uttid=False):
    """
    Read an alignment file generated by wer_per_utt_details.pl.
    """
    with open(file, "r") as f:
        lines = [re.sub(' +', ' ', line) for line in f.readlines()]
        fname = lines[0].strip()
        uttid = lines[1].strip().split(" ")[0]
        ref = lines[1].strip().split(" ")[2:]
        hyp = lines[2].strip().split(" ")[2:]
        op = lines[3].strip().split(" ")[2:]
        csid = lines[4].strip().split(" ")[2:]

    if return_uttid:
        return fname, uttid, ref, hyp, op, csid
    return fname, ref, hyp, op, csid


def read_pdump_file(dump):
    """
    Read the dump file of primary alignment.
    """
    res = {}
    with open(dump, "r") as f:
        for line in f:
            hyp, ref, stats = line.strip().split(maxsplit=2)
            stats = stats.split()
            csid = [int(stat) for stat in stats[:4]]
            length = int(stats[4])
            cratio = float(stats[-1])
            res[ref] = dict(hyp=hyp, csid=csid, length=length, cratio=cratio)
    return res


def parse_segments_file(fp):
    res = {}
    for line in fp:
        segid, _, start, end = line.strip().split(" ")
        res[segid] = {"start": start, "end": end}
    return res


class Integerizer():
    def __init__(self, tokens: List):
        self.token2int = {}
        self.int2token = []
        for token in tokens:
            if token not in self.token2int:
                self.token2int[token] = len(self.token2int)
                self.int2token.append(token)

    @overload
    def __getitem__(self, index: int):
        ...

    @overload
    def __getitem__(self, index: slice) -> List:
        ...

    def __getitem__(self, index):
        return self.int2token[index]

    def index(self, token):
        assert type(token) in [str, list]
        return self.token2int[token] if type(token) == str else [self.token2int[t] for t in token]

    def store_vocab(self, output):
        # Store the vocab as a json object
        with open(output, "w") as f:
            json.dump({"token2int": self.token2int, "int2token": self.int2token}, f)

    def load_vocab(self, vocab):
        # Load the vocab from a json file
        with open(vocab, "r") as f:
            vocab_info = json.load(f)
            self.token2int, self.int2token = vocab_info["token2int"], vocab_info["int2token"]


def levenshtein(str1, str2):
    txt1, txt2 = str1.strip().split(" "), str2.strip().split(" ")

    # Integerize the input strings
    vocab = Integerizer(txt1 + txt2)
    tokens1, tokens2 = np.array(vocab.index(txt1)), np.array(vocab.index(txt2))

    dp = np.full((len(tokens1) + 1, len(tokens2) + 1),
                 np.iinfo(np.int32).max, dtype=np.int32)
    pointers = np.full((len(tokens1) + 1, len(tokens2) + 1, 2), (0, 0))

    # Initialize the matrix
    dp[0, 0] = 0
    for row in range(1, dp.shape[0]):
        dp[row, 0] = row
        pointers[row, 0] = (row - 1, 0)
    for col in range(1, dp.shape[1]):
        dp[0, col] = col
        pointers[0, col] = (0, col - 1)

    # Start DP
    for row in range(1, dp.shape[0]):
        for col in range(1, dp.shape[1]):
            if tokens1[row - 1] == tokens2[col - 1]:
                dp[row, col] = dp[row - 1, col - 1]
                pointers[row, col] = [row - 1, col - 1]
            else:
                a = dp[row - 1: row + 1, col - 1: col + 1]
                sub_index = np.unravel_index(np.argmin(a, axis=None), a.shape)
                min_index = np.array([sub_index[0] + row - 1, sub_index[1] + col - 1])
                pointers[row, col] = min_index
                p0, p1 = min_index
                dp[row, col] = dp[p0, p1] + 1

    # Backtrace to highlight duplicates
    backpointer = np.array([len(tokens1), len(tokens2)])
    res1_raw, res2_raw = [], []
    need_closure1, need_closure2 = False, False
    while (backpointer != [0, 0]).any():
        # print(backpointer)
        if dp[backpointer[0], backpointer[1]] == dp[pointers[backpointer[0], backpointer[1]][0], pointers[backpointer[0], backpointer[1]][1]]:
            if need_closure1:
                res1_raw.append(txt1[backpointer[0] - 1])
            else:
                res1_raw.extend(["]", txt1[backpointer[0] - 1]])
                need_closure1 = True
            if need_closure2:
                res2_raw.append(txt2[backpointer[1] - 1])
            else:
                res2_raw.extend(["]", txt2[backpointer[1] - 1]])
                need_closure2 = True
        else:
            if pointers[backpointer[0], backpointer[1]][0] != backpointer[0]:
                if need_closure1:
                    res1_raw.extend(["[", txt1[backpointer[0] - 1]])
                    need_closure1 = False
                    res2_raw.extend(["["])
                    need_closure2 = False
                else:
                    res1_raw.append(txt1[backpointer[0] - 1])
            if pointers[backpointer[0], backpointer[1]][1] != backpointer[1]:
                if need_closure2:
                    res1_raw.extend(["["])
                    need_closure1 = False
                    res2_raw.extend(["[", txt2[backpointer[1] - 1]])
                    need_closure2 = False
                else:
                    res2_raw.append(txt2[backpointer[1] - 1])
        backpointer = pointers[backpointer[0], backpointer[1]]

    res1_raw.reverse()
    res2_raw.reverse()

    res1, res2 = " ".join(res1_raw), " ".join(res2_raw)

    return dp[-1, -1], res1, res2
