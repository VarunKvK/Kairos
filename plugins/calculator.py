"""
plugins/calculator.py — Safe Math Calculator
Evaluates mathematical expressions safely.
No eval() — uses Python's ast module.
"""

import ast
import operator

PLUGIN_NAME        = "calculator"
PLUGIN_DESCRIPTION = "Safely evaluate mathematical expressions"
PLUGIN_ACTIONS     = ["calculate"]

# Allowed operators — no dangerous operations
_OPERATORS = {
    ast.Add:  operator.add,
    ast.Sub:  operator.sub,
    ast.Mult: operator.mul,
    ast.Div:  operator.truediv,
    ast.Pow:  operator.pow,
    ast.Mod:  operator.mod,
    ast.USub: operator.neg,
}


def _safe_eval(node):
    """Recursively evaluate AST nodes — only allows math operations."""
    if isinstance(node, ast.Constant):
        return node.value
    elif isinstance(node, ast.BinOp):
        op = _OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Operator not allowed: {node.op}")
        return op(_safe_eval(node.left), _safe_eval(node.right))
    elif isinstance(node, ast.UnaryOp):
        op = _OPERATORS.get(type(node.op))
        if not op:
            raise ValueError(f"Operator not allowed: {node.op}")
        return op(_safe_eval(node.operand))
    else:
        raise ValueError(f"Expression type not allowed: {node}")


def run(action: str, input: str) -> str:
    """
    Calculate a math expression.

    Input: any math expression e.g. "2 + 2", "10 * 3.14", "2 ** 10"
    """
    if action != "calculate":
        return f"Unknown action: {action}"

    expression = input.strip()

    if not expression:
        return "No expression provided."

    try:
        tree   = ast.parse(expression, mode="eval")
        result = _safe_eval(tree.body)

        # Format cleanly — int if possible
        if isinstance(result, float) and result.is_integer():
            result = int(result)

        return f"{expression} = {result}"

    except ZeroDivisionError:
        return "Error: division by zero."
    except Exception as e:
        return f"Could not calculate '{expression}': {e}"