#!/usr/bin/env bash
# Build helix-cal-loop.wav — the loudness-normalization calibration stimulus.
#
# 10 single notes E2..C5, 0.5 s each, concatenated to EXACTLY 240000 samples
# (5.00 s at 48 kHz). The exact 5.00 s cycle is the point: a measurement window
# that does not cover whole loop cycles reports a misleading number, because the
# loop's own level contour lands differently in every window.
#
# Source: FreePats "FSBS Electric Guitar Direct" — raw unprocessed guitar DI,
# CC0 1.0 public domain. The bank ships individual sampled notes, not riffs, so
# the loop is assembled rather than found.
#
# Requires: sox, curl, tar (macOS tar reads .7z via libarchive — no p7zip needed).
set -euo pipefail

# Work beside this script, not in $PWD — otherwise running it from the repo root
# regenerates nothing useful and litters ~100 MB of archive and samples there.
cd "$(dirname "$0")"

ARCHIVE=EGuitarFSBS-bridge-direct-SFZ+FLAC-20220911.7z
URL="https://freepats.zenvoid.org/ElectricGuitar/FSBS-EGuitar/${ARCHIVE}"
TREE=EGuitarFSBS-bridge-direct-SFZ+FLAC-20220911
SRC="$TREE/samples"
OUT=helix-cal-loop.wav

# -f so an HTTP error page isn't silently written into $ARCHIVE and handed to tar.
if [ ! -d "$SRC" ]; then
  curl -fsSL -o "$ARCHIVE" "$URL"
  tar -xf "$ARCHIVE"
fi
trap 'rm -rf "$ARCHIVE" "$TREE"' EXIT

# -r/-c are passed explicitly so the output can't silently inherit a different
# source format. These notes are already 48 kHz/24-bit/mono.
i=0
for n in E2_s1 A2_s2 C3_s2 D3_s3 E3_s3 G3_s4 B3_s5 E4_s6 G4_s6 C5_s6; do
  i=$((i + 1))
  sox "$SRC/${n}_01.flac" -b 24 -r 48000 -c 1 "$(printf 'v2n%02d' $i).wav" \
      trim 0 0.5 fade 0.003 0.5 0.06
done

# gain -n -3 normalizes the CONCATENATED file to -3 dBFS peak: plain `gain -3`
# attenuates rather than normalizes (so it would not deliver the stated peak),
# and a per-note `gain -n` would flatten the relative dynamics between notes.
# -3 dBFS is intersample-peak margin for the OS resampler — it buys no analog
# headroom, which is set entirely by the Mac volume notch and the input Pad.
sox v2n01.wav v2n02.wav v2n03.wav v2n04.wav v2n05.wav \
    v2n06.wav v2n07.wav v2n08.wav v2n09.wav v2n10.wav \
    "$OUT" gain -n -3

rm -f v2n[0-9][0-9].wav

# The one property everything downstream rests on.
samples=$(sox --i -s "$OUT")
[ "$samples" = 240000 ] || { echo "FAIL: $OUT is $samples samples, expected 240000 (5.00 s)" >&2; exit 1; }

echo "OK: $OUT"
sox --i "$OUT" | grep -E 'Channels|Sample Rate|Precision|Duration'
sox "$OUT" -n stats 2>&1 | grep -E 'Pk lev dB|RMS lev dB'
