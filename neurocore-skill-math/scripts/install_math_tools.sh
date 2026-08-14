#!/usr/bin/env bash
# install_math_tools.sh — check & install/update the math-proof toolchain for
# neurocore-skill-math on Ubuntu 24.04.
#
# Idempotent: each tool is installed only if missing or outdated.
# Usage:
#   ./install_math_tools.sh            # install everything
#   ./install_math_tools.sh --report   # print availability report and exit
#   ./install_math_tools.sh --no-sage --no-isabelle --no-lean --no-julia-pkg

set -uo pipefail

VENV="${VENV:-$HOME/.venvs/neurocore-math}"
MATH_HOME="${MATH_HOME:-$HOME/math-agents}"
DO_SAGE=1; DO_ISABELLE=1; DO_LEAN=1; DO_COQ_OPAM=0; DO_JULIA_PKG=1; REPORT_ONLY=0

for arg in "$@"; do
  case "$arg" in
    --report) REPORT_ONLY=1 ;;
    --no-sage) DO_SAGE=0 ;;
    --no-isabelle) DO_ISABELLE=0 ;;
    --no-lean) DO_LEAN=0 ;;
    --coq-opam) DO_COQ_OPAM=1 ;;
    --no-julia-pkg) DO_JULIA_PKG=0 ;;
    *) echo "unknown flag: $arg"; exit 2 ;;
  esac
done

have() { command -v "$1" >/dev/null 2>&1; }
have_julia_pkg() { 
  if ! have julia; then return 1; fi
  julia -e "using $1" >/dev/null 2>&1
}

say()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m[✓]\033[0m %s\n' "$*"; }
miss() { printf '  \033[31m[✗]\033[0m %s\n' "$*"; }

report() {
  say "Tool availability"
  for t in gp gap sage docker z3 cvc5 vampire eprover prover9 mace4 \
           lean lake elan isabelle coqc maxima singular M2 julia; do
    if have "$t"; then ok "$t"; else miss "$t"; fi
  done

  say "Julia Math Packages"
  for jp in Oscar HomotopyContinuation; do
    if have_julia_pkg "$jp"; then ok "$jp"; else miss "$jp"; fi
  done

  if [ -n "${CONDA_PREFIX:-}" ]; then
    say "Conda environment ($CONDA_DEFAULT_ENV)"
    python - <<'PY' 2>/dev/null || echo "  (conda python not usable)"
import importlib.util as u
for m in ["sympy","numpy","scipy","mpmath","z3","cvc5","networkx",
          "neurocore","neurocore_skill_math", "wolframalpha", "lean_dojo_v2"]:
    print(f"  [{'✓' if u.find_spec(m) else '✗'}] {m}")
PY
  elif [ -d "$VENV" ]; then
    say "Python math venv ($VENV)"
    "$VENV/bin/python" - <<'PY' 2>/dev/null || echo "  (venv python not usable)"
import importlib.util as u
for m in ["sympy","numpy","scipy","mpmath","z3","cvc5","networkx",
          "neurocore","neurocore_skill_math", "wolframalpha", "lean_dojo_v2"]:
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

# --- A. apt base packages (with Macaulay2 and Julia additions) ----------------
say "A. apt base + tools (including Macaulay2 and Julia)"
sudo apt update -y

PKGS=(
  build-essential git curl wget unzip jq python3 python3-pip python3-venv
  pkg-config cmake ninja-build software-properties-common
  default-jre default-jdk opam
  pari-gp gap gap-core gap-dev coq z3 cvc5 eprover prover9 mace4
  singular maxima graphviz vampire macaulay2 julia
)

for pkg in "${PKGS[@]}"; do
  if apt-cache show "$pkg" >/dev/null 2>&1; then
    sudo apt install -y "$pkg"
  else
    echo "  (package $pkg is not available on mirror - skipping)"
  fi
done


# --- B. Python math environment setup -----------------------------------------
if [ -n "${CONDA_PREFIX:-}" ]; then
  say "B. Python environment (Conda Active: $CONDA_DEFAULT_ENV)"
  pip install --upgrade pip setuptools wheel
  pip install --upgrade \
    sympy numpy scipy mpmath z3-solver cvc5 networkx pandas matplotlib \
    hypothesis pytest pydantic pyyaml rich wolframalpha lean-dojo-v2
  pip install --upgrade "neurocore-ai>=0.3.0" "neurocore-skill-math"
  ok "Conda active environment upgraded: $CONDA_DEFAULT_ENV"
else
  say "B. Python venv ($VENV)"
  if [ ! -d "$VENV" ]; then python3 -m venv "$VENV"; fi
  # shellcheck disable=SC1091
  source "$VENV/bin/activate"
  python -m pip install --upgrade pip setuptools wheel
  python -m pip install --upgrade \
    sympy numpy scipy mpmath z3-solver cvc5 networkx pandas matplotlib \
    hypothesis pytest pydantic pyyaml rich wolframalpha lean-dojo-v2
  python -m pip install --upgrade "neurocore-ai>=0.3.0" "neurocore-skill-math"
  ok "venv ready: source $VENV/bin/activate"
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

# --- E. Isabelle + AFP ------------------------------------------------------
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

# --- F. Coq via opam (optional, newer than apt) -----------------------------
if [ "$DO_COQ_OPAM" = 1 ]; then
  say "F. Coq via opam"
  opam init -y --disable-sandboxing && eval "$(opam env)"
  opam repo add coq-released https://coq.inria.fr/opam/released || true
  opam install -y coq && eval "$(opam env)"
fi

# --- G. Julia Packages (OSCAR & HomotopyContinuation) -----------------------
if [ "$DO_JULIA_PKG" = 1 ] && have julia; then
  say "G. Julia Packages (OSCAR & HomotopyContinuation)"
  julia -e '
    using Pkg
    pkgs = ["Oscar", "HomotopyContinuation"]
    for p in pkgs
      if !haskey(Pkg.project().dependencies, p)
        @info "Installing package: $p"
        Pkg.add(p)
      else
        @info "Package $p already installed, updating..."
        Pkg.update(p)
      end
    end
  '
fi

report
say "Done. Verify with: python -m neurocore_skill_math.check"
