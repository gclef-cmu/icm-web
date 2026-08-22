"""``{solution}`` without a label — an answer the reader reveals on click.

Upstream sphinx-exercise pairs a solution to an exercise by label, as a
separate block::

    :::{exercise}
    :label: ex-nyquist
    State the Nyquist frequency for a 48 kHz sample rate.
    :::

    :::{solution} ex-nyquist
    24 kHz — half the sample rate.
    :::

That form still works exactly as before. What this adds is a solution with
**no label argument**, which belongs inside the exercise it answers::

    ::::{exercise}
    State the Nyquist frequency for a 48 kHz sample rate.

    :::{solution}
    24 kHz — half the sample rate.
    :::
    ::::

It renders as a "Reveal solution" button inside the exercise box, with the
answer hidden until the reader clicks it (a native ``<details>``, so it works
with JavaScript off). Note the outer fence grows to ``::::`` so the nested
``:::`` closes inside it. An exercise with no solution is untouched.

The ``:class:`` and ``:hidden:`` options carry over from upstream, as does the
``hide_solutions`` config value — setting it strips these solutions too, so a
student-facing build doesn't leak answers.
"""
from __future__ import annotations

from html import escape

from docutils import nodes
from sphinx.application import Sphinx
from sphinx.util.docutils import SphinxDirective

try:
    from sphinx_exercise.directive import SolutionDirective as _BaseSolution
except ImportError:  # sphinx-exercise absent: only the unlabeled form is served
    _BaseSolution = SphinxDirective
    _HAS_UPSTREAM = False
else:
    _HAS_UPSTREAM = True

_BUTTON_LABEL = "Reveal solution"


class reveal_solution(nodes.General, nodes.Element):
    """Solution body that renders as a ``<details>`` disclosure in HTML."""


class SolutionDirective(_BaseSolution):  # type: ignore[misc, valid-type]
    """``{solution}`` — upstream's when given an exercise label, ours without.

    Subclassing keeps the labeled form byte-identical to upstream: the only
    change is that the argument became optional, and an omitted one routes to
    the reveal-on-click node instead.
    """

    has_content = True
    required_arguments = 0
    optional_arguments = 1
    final_argument_whitespace = False
    option_spec = dict(getattr(_BaseSolution, "option_spec", None) or {})

    def run(self) -> list[nodes.Node]:
        if self.arguments and _HAS_UPSTREAM:
            return super().run()  # ``{solution} <exercise-label>``, unchanged

        # Both of upstream's ways to drop a solution from the output.
        if getattr(self.env.config, "hide_solutions", False):
            return []
        if "hidden" in self.options:
            return []

        node = reveal_solution()
        node["classes"] = self.options.get("class", [])
        self.set_source_info(node)
        self.state.nested_parse(self.content, self.content_offset, node)
        return [node]


def visit_reveal_solution_html(self, node: reveal_solution) -> None:
    classes = " ".join(["exercise-solution", *node.get("classes", [])])
    self.body.append(
        f'<details class="{escape(classes, quote=True)}">'
        f"<summary>{escape(_BUTTON_LABEL)}</summary>"
        '<div class="exercise-solution-body">'
    )


def depart_reveal_solution_html(self, node: reveal_solution) -> None:
    self.body.append("</div></details>")


def visit_reveal_solution_latex(self, node: reveal_solution) -> None:
    # Nothing to click in a PDF, so the answer just prints, labeled.
    self.body.append("\n\n\\noindent\\textbf{Solution.}\\quad ")


def depart_reveal_solution_latex(self, node: reveal_solution) -> None:
    self.body.append("\n")


def setup(app: Sphinx) -> dict:
    if _HAS_UPSTREAM:
        # Load sphinx-exercise first, so registering `solution` overrides its
        # directive rather than being overridden by it.
        app.setup_extension("sphinx_exercise")
    app.add_node(
        reveal_solution,
        html=(visit_reveal_solution_html, depart_reveal_solution_html),
        latex=(visit_reveal_solution_latex, depart_reveal_solution_latex),
    )
    app.add_directive("solution", SolutionDirective, override=True)
    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
