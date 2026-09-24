"""Model adapters. Each adapter returns a DecisionResult.

Every adapter exposes the same probabilities-over-exact-labels interface:
  * TypeSafe-compatible /v1/systemone (native typed interface).
  * The list-shaped /decide flavour some open rebuilds ship (also native).
  * A Gradio demo Space, when that is a rebuild's only public interface
    (still the model's own softmax, only the transport is the demo form).
  * An open-weights checkpoint loaded in-process (native softmax, no network).
  * OpenAI-compatible chat completions with JSON-schema-constrained output;
    the distribution is VERBALIZED by the model (we ask it to emit
    probabilities). This is explicitly NOT logprobs.

No silent fallback: if the endpoint URL/model/key is missing or the response
is unusable, the adapter raises and the runner records a failed attempt.
Raw provider responses are preserved by the runner, not here.
"""

from .base import DecisionResult  # noqa: F401
from .typesafe import TypeSafeAdapter  # noqa: F401
from .openai_compat import OpenAICompatAdapter  # noqa: F401
from .systemone_list import SystemOneListAdapter  # noqa: F401
from .gradio_space import GradioSpaceAdapter  # noqa: F401
from .local_openjev import LocalOpenJevAdapter  # noqa: F401
from .semif_direct import SemIfDirectAdapter  # noqa: F401
from .so1_decider import So1DeciderAdapter  # noqa: F401
from .remote_inproc import RemoteInprocAdapter  # noqa: F401
from .sg_system_one import SgSystemOneAdapter  # noqa: F401
from .djev import DjevAdapter  # noqa: F401
# v1.2.2 additions (their heavy libraries are imported lazily, inside each system's own venv)
from .laya_local import LayaLocalAdapter  # noqa: F401
from .gliner2_local import Gliner2LocalAdapter  # noqa: F401
from .verdict_local import VerdictLocalAdapter  # noqa: F401
from .paw_local import PawLocalAdapter  # noqa: F401
from .classifier_dev import ClassifierDevAdapter  # noqa: F401
from .certo_local import CertoLocalAdapter  # noqa: F401
from .smalljev_local import SmallJevLocalAdapter  # noqa: F401
from .verdictml_local import VerdictMlLocalAdapter  # noqa: F401


def NeedleLocalAdapter(**kw):  # lazy: only the Needle venv can import needle
    from .needle_local import NeedleLocalAdapter as A
    return A(**kw)

from .qwen_flash_linear import QwenFlashLinearAdapter  # noqa: F401
