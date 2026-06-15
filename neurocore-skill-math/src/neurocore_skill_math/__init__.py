"""neurocore-skill-math — a math-proof toolchain for NeuroCore.

One package exposing many small composable skills (CAS, SMT, ATP, formal proof
assistants). Each skill detects whether its backend tool is installed and degrades
gracefully when it is not (status ``tool_unavailable``).
"""
from neurocore_skill_math.atp import (
    EproverProveTptpSkill,
    Mace4CountermodelSkill,
    Prover9ProveSkill,
    VampireProveTptpSkill,
)
from neurocore_skill_math.cas import (
    GapGroupTheorySkill,
    PariGpNumberTheorySkill,
    SagemathComputeSkill,
)
from neurocore_skill_math.formal import (
    CoqCheckSkill,
    IsabelleCheckTheorySkill,
    Lean4CheckSkill,
    Lean4FormalizeStatementSkill,
    Lean4RepairSkill,
)
from neurocore_skill_math.numeric import MpmathHighPrecisionCheckSkill
from neurocore_skill_math.planning import LlmProofPlannerSkill, TheoremRetrieverSkill
from neurocore_skill_math.prep import (
    MathDomainClassifierSkill,
    MathProblemParserSkill,
    MathStatementNormalizerSkill,
)
from neurocore_skill_math.report import ProofReportBuilderSkill
from neurocore_skill_math.smt import Cvc5SmtCheckSkill, Z3SmtCheckSkill
from neurocore_skill_math.symbolic import (
    SympyCalculusSkill,
    SympySimplifySkill,
    SympySolveSkill,
)

__all__ = [
    # Group 1 — prep
    "MathProblemParserSkill",
    "MathDomainClassifierSkill",
    "MathStatementNormalizerSkill",
    # Group 2 — symbolic / numeric / CAS
    "SympySimplifySkill",
    "SympySolveSkill",
    "SympyCalculusSkill",
    "MpmathHighPrecisionCheckSkill",
    "SagemathComputeSkill",
    "PariGpNumberTheorySkill",
    "GapGroupTheorySkill",
    # Group 3 — counterexample / SMT
    "Z3SmtCheckSkill",
    "Cvc5SmtCheckSkill",
    "Mace4CountermodelSkill",
    # Group 4 — ATP
    "VampireProveTptpSkill",
    "EproverProveTptpSkill",
    "Prover9ProveSkill",
    # Group 4/5 — planning, retrieval
    "LlmProofPlannerSkill",
    "TheoremRetrieverSkill",
    # Group 5 — formalization
    "Lean4FormalizeStatementSkill",
    "Lean4CheckSkill",
    "Lean4RepairSkill",
    "IsabelleCheckTheorySkill",
    "CoqCheckSkill",
    # Group 6 — reporting
    "ProofReportBuilderSkill",
]
