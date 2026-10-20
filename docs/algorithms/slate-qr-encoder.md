---
title: The slate's QR encoder
source: slate/index.html:QR.encode (JavaScript; kept by hand, the checker reads Python only)
refs: [iso18004_2015, reed1960]
status: draft
---

# The slate's QR encoder

**Code:** `slate/index.html`, between the `qr-encoder:begin` / `qr-encoder:end` markers
(lines 224–490): `dataCodewords` (248), `gfMul` (254), `rsDivisor` (262), `rsRemainder` (275),
`buildCodewords` (286), `encode` (328); the payload and drawing are `slatePayload` /
`syncPayload` (530–531) and `drawQR` (537).
**Tested by:** `tests/test_slate.py` (runs this code in Node and decodes every symbol with
OpenCV; skipped without Node).

**What it does.** Turns a text payload such as `pk1:20260212_hooper1_vertical-swimming:take03`
into a square matrix of dark and light modules, a QR Code symbol, in byte mode, versions 1–10,
any of the four error-correction levels (the page always asks for **M**). It is hand-written so
the page needs no downloads. Input: a string (UTF-8 encoded). Output: `{version, size, modules}`,
`size` × `size` booleans, dark = `true`. The page then draws it with a 4-module white quiet zone
at a whole number of device pixels per module.

## Method

**Symbol size and version.** A version-$v$ symbol is $n = 4v + 17$ modules on a side. The
encoder takes the smallest $v \le 10$ whose data capacity holds the payload:

$$
4 + c(v) + 8L \;\le\; 8\,D(v,\ell), \qquad
c(v) = \begin{cases} 8 & v \le 9 \\ 16 & v = 10 \end{cases}, \qquad
D(v,\ell) = n_1 d_1 + n_2 d_2
$$

where $L$ is the payload length in bytes, 4 bits are the mode indicator (`0100`, byte mode),
$c(v)$ the character-count field, and $D$ the data codewords of version $v$ at level $\ell$:
$n_1$ blocks of $d_1$ codewords plus $n_2$ blocks of $d_2$ (the `BLOCKS` table). At level M,
version 4 holds $D = 2 \times 32 = 64$ codewords, so payloads up to 62 bytes — the typical slate
payload — fit a 33 × 33 symbol.

**Data bits.** Mode, count, the bytes, a terminator of up to four zero bits, zero bits to a
byte boundary, then the pad bytes `0xEC`, `0x11` alternately until $D$ codewords.

**Error correction (Reed–Solomon).** Arithmetic is in GF($2^8$) with the primitive polynomial
$p(x) = x^8 + x^4 + x^3 + x^2 + 1$ (`0x11D`) and $\alpha = 2$. For a block with $e$ error-correction
codewords, the generator is

$$
g(x) = \prod_{i=0}^{e-1} \left(x - \alpha^{i}\right),
$$

and the error-correction codewords are the remainder $m(x)\,x^{e} \bmod g(x)$ of the block's data
polynomial $m(x)$ (`rsDivisor`, `rsRemainder`). Blocks are interleaved codeword by codeword: all
blocks' first data codewords, then their second, … , then the same for the EC codewords.

**Format information (15 bits).** Five data bits $f = (\text{level} \ll 3) \,|\, \text{mask}$, with
level bits L = 01, M = 00, Q = 11, H = 10, extended by a BCH(15,5) remainder with generator
$x^{10} + x^8 + x^5 + x^4 + x^2 + x + 1$ (`0x537`) and XORed with `0x5412`; drawn twice, beside the
finders.

**Version information (18 bits, $v \ge 7$).** $v$ extended by a BCH(18,6) remainder with generator
$x^{12} + x^{11} + x^{10} + x^9 + x^8 + x^5 + x^2 + 1$ (`0x1F25`), drawn in two 6 × 3 blocks.

**Masking.** Each of the eight masks $M_k(x, y)$ (e.g. $M_0: (x + y) \bmod 2 = 0$) is applied in turn
by XOR to the non-function modules, and the one with the lowest penalty is kept:

$$
P = \sum_{\text{runs} \ge 5} \left(3 + (r - 5)\right) \;+\; 3\,N_{2\times2} \;+\; 40\,N_{\text{finder-like}}
\;+\; 10 \left\lfloor \frac{\left|20\,n_\text{dark} - 10\,n^2\right|}{n^2} \right\rfloor
$$

over rows and columns: $r$ is the length of a run of same-colour modules, $N_{2\times2}$ the number of
2 × 2 same-colour squares, $N_\text{finder-like}$ the occurrences of the 11-module patterns
`1011101 0000` and `0000 1011101`, and the last term is 10 points per 5 % that the dark fraction
departs from 50 %.

All the numbers above — the capacity table, alignment-pattern positions, `0x11D`, `0x537`,
`0x5412`, `0x1F25`, the masks and the penalty weights — are **published**, from the QR Code
standard [iso18004_2015] (Reed–Solomon codes in general: [reed1960]). They were not checked
against the standard's text here (it is paywalled); the tests check them by decoding.

**Ours:** level **M** (`drawQR`, line 538); versions **1–10 only** (a slate payload is under 80
bytes, version 10 at M holds 213); **whole device pixels per module** (line 542: a fractional
scale smears module edges); and the payload grammar `pk1:<id>:takeNN[:sync:KKKK]` with the id
rule `^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$` and no `..` (lines 499, 525–531). The 4-module quiet
zone (line 500) is the standard's.

## Steps

```text
encode(text, level = "M"):
    bytes   <- UTF-8 of text
    v       <- smallest v in 1..10 with 4 + c(v) + 8*len(bytes) <= 8*D(v, level)   else error
    n       <- 4v + 17
    draw function patterns: timing rows/cols 6, three finders + separators,
        alignment patterns (ALIGN[v], skipping the finder corners), format area reserved,
        version blocks if v >= 7
    codewords <- buildCodewords(bytes, v, level):
        bits = 0100 | count | bytes | terminator | byte-align | pad 0xEC,0x11,...
        split into blocks (BLOCKS[level][v]); ec = rsRemainder(block, g_e)
        interleave data codewords, then ec codewords
    place codeword bits in 2-module columns from the right, zig-zagging up and down,
        skipping column 6 and every function module
    for mask in 0..7: apply, draw format bits, score P, un-apply
    apply the best mask; draw its format bits
    return {version v, size n, modules}
```

## Sources

[iso18004_2015] (candidate: cited in the code, not read here); [reed1960] (candidate). The
encoder's structure is the standard one; the code itself is the lab's.

## Limits

- **A wrong table entry does not throw.** It draws a symbol that may not decode, or decodes only
  sometimes. That is why `tests/test_slate.py` decodes every version at every level, including
  each version's first and last payload length. Those tests **skip without Node**, and Node was not
  on the PATH of the machine this page was written on (2026-10-20) — wherever that is true, the
  encoder goes unchecked while the suite still reports green.
- **Byte mode only.** Fine for the slate (the id rule keeps payloads ASCII); a long payload in
  alphanumeric mode would fit a smaller symbol, but nothing here needs it.
- **The penalty only chooses the mask.** Any of the eight masks gives a valid symbol, so a slip in
  the penalty score makes a symbol a little harder to read, never wrong.
- **The QR never inverts during sync**: light-on-dark codes defeat many decoders, OpenCV's among
  them (`slate/README.md`).
