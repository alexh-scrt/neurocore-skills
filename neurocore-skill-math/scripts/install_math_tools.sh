#!/usr/bin/env bash
# install_math_tools.sh — check & install the math-proof toolchain for
# neurocore-skill-math on Ubuntu 24.04.
#
# Idempotent: each tool is installed only if missing. Heavyweight assistants
# (Lean+Mathlib, Isabelle+AFP, SageMath) are large; flags let you skip them.
#
# Usage:
#   ./install_math_tools.sh            # install everything (apt + python + lean + sage…)
#   ./install_math_tools.sh --report   # only print an availability report and exit
#   ./install_math_tools.sh --no-sage --no-isabelle --no-lean
#   VENV=~/.venvs/neurocore-math ./install_math_tools.sh
set -uo pipefail

VENV="${VENV:-$HOME/.venvs/neurocore-math}"
MATH_HOME="${MATH_HOME:-$HOME/math-agents}"
DO_SAGE=1; DO_ISABELLE=1; DO_LEAN=1; DO_COQ_OPAM=0; REPORT_ONLY=0
for arg in "$@"; do
  case "$arg" in
    --report) REPORT_ONLY=1 ;;
    --no-sage) DO_SAGE=0 ;;
    --no-isabelle) DO_ISABELLE=0 ;;
    --no-lean) DO_LEAN=0 ;;
    --coq-opam) DO_COQ_OPAM=1 ;;
    *) echo "unknown flag: $arg"; exit 2 ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }
say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m[✓]\033[0m %s\n' "$*"; }
miss() { printf '  \033[31m[✗]\033[0m %s\n' "$*"; }

report() {
  say "Tool availability"
  for t in gp gap sage docker z3 cvc5 vampire eprover prover9 mace4 \
           lean lake elan isabelle coqc maxima singular; do
    if have "$t"; then ok "$t"; else miss "$t"; fi
  done
  if [ -d "$VENV" ]; then
    say "Python math venv ($VENV)"
    "$VENV/bin/python" - <<'PY' 2>/dev/null || echo "  (venv python not usable)"
import importlib.util as u
for m in ["sympy","numpy","scipy","mpmath","z3","cvc5","networkx",
          "neurocore","neurocore_skill_math"]:
    print(f"  [{'✓' if u.find_spec(m) else '✗'}] {m}")
PY
  fi
}

if [ "$REPORT_ONLY" = 1 ]; then report; exit 0; fi

if [ "$(uname -s)" != "Linux" ]; then
  echo "This installer targets Ubuntu 24.04 (Linux). On $(uname -s), use it only"
  echo "with --report, or install tools via your platform's package manager."
  report; exit 1
fi

# --- A. apt base packages ---------------------------------------------------
say "A. apt base + tools"
sudo apt update -y
sudo apt install -y \
  build-essential git curl wget unzip jq python3 python3-pip python3-venv \
  pkg-config cmake ninja-build software-properties-common \
  default-jre default-jdk opam \
  pari-gp gap gap-core gap-dev coq z3 cvc5 eprover prover9 mace4 \
  singular maxima graphviz vampire || \
  echo "  (some apt packages may be unavailable on your mirror — see notes)"

# --- B. Python math venv ----------------------------------------------------
say "B. Python venv ($VENV)"
if [ ! -d "$VENV" ]; then python3 -m venv "$VENV"; fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install --upgrade pip setuptools wheel
python -m pip install --upgrade \
  sympy numpy scipy mpmath z3-solver cvc5 networkx pandas matplotlib \
  hypothesis pytest pydantic pyyaml rich
python -m pip install --upgrade "neurocore-ai>=0.3.0" "neurocore-skill-math"
ok "venv ready: source $VENV/bin/activate"

# --- D. Lean 4 + Mathlib ----------------------------------------------------
if [ "$DO_LEAN" = 1 ]; then
  say "D. Lean 4 + Mathlib (elan)"
  if ! have elan; then
    curl https://raw.githubusercontent.com/leanprover/elan/master/elan-init.sh -sSf | sh -s -- -y
    # shellcheck disable=SC1091
    source "$HOME/.elan/env"
  fi
  if [ ! -d "$MATH_HOME/MathAgent" ]; then
    mkdir -p "$MATH_HOME"; (cd "$MATH_HOME" \
      && lake +leanprover-community/mathlib4:lean-toolchain new MathAgent math \
      && cd MathAgent && lake update && lake exe cache get && lake build)
  fi
  ok "Lean project at $MATH_HOME/MathAgent (set lean4_check project_root to it)"
fi

# --- F. Coq via opam (optional, newer than apt) -----------------------------
if [ "$DO_COQ_OPAM" = 1 ]; then
  say "F. Coq via opam"
  opam init -y --disable-sandboxing && eval "$(opam env)"
  opam repo add coq-released https://coq.inria.fr/opam/released || true
  opam install -y coq && eval "$(opam env)"
fi

# --- C. SageMath ------------------------------------------------------------
if [ "$DO_SAGE" = 1 ]; then
  say "C. SageMath"
  if have sage; then ok "sage already installed"
  elif have docker; then docker pull sagemath/sagemath:latest && \
    ok "Sage via Docker (sagemath_compute uses a sandboxed container)"
  elif have micromamba; then micromamba create -n sage -c conda-forge sage python=3.11 -y && \
    ok "Sage via micromamba (activate: micromamba activate sage)"
  else miss "No sage/docker/micromamba — install one (see design/math_skills.md §C)"; fi
fi

# --- E. Isabelle + AFP (manual download; version-specific) ------------------
if [ "$DO_ISABELLE" = 1 ] && ! have isabelle; then
  say "E. Isabelle/HOL + AFP — manual step"
  cat <<'TXT'
  Download the current Linux build from https://isabelle.in.tum.de and:
    tar -xzf Isabelle*_linux.tar.gz -C ~/opt
    echo 'export PATH="$HOME/opt/Isabelle<VER>/bin:$PATH"' >> ~/.bashrc
  Then register the matching AFP:
    isabelle components -u ~/opt/afp/thys
TXT
fi

report
say "Done. Verify with: python -m neurocore_skill_math.check"
