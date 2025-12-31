import sys

import numpy as np
from PIL import Image

img1 = np.array(Image.open(sys.argv[1]).convert("RGB"), dtype=np.int32)
img2 = np.array(Image.open(sys.argv[2]).convert("RGB"), dtype=np.int32)

diff = np.sum((img1 - img2) ** 2, axis=2)
total = diff.size
non_matching = np.count_nonzero(diff)

print(f"Non-matching pixels: {non_matching} ({100 * non_matching / total:.2f}%)")
if non_matching > 0:
  quantiles = [25, 50, 75, 90, 95, 99, 99.9]
  res = np.percentile(diff, [25, 50, 75, 90]).astype(int).tolist()
  for q, r in zip(quantiles, res, strict=True):
    print(q, r)
