# Expression Parser Spec

Implement a recursive descent parser for arithmetic expressions in Python.

## Grammar

    expr    ::= term (('+' | '-') term)*
    term    ::= factor (('*' | '/') factor)*
    factor  ::= unary | primary
    unary   ::= '-' factor
    primary ::= NUMBER | '(' expr ')'
    NUMBER  ::= [0-9]+ ('.' [0-9]+)?

## Requirements

- `parse(expression: str) -> float` — top-level entry point
- Evaluates the expression and returns the numeric result as a float
- Operator precedence: * and / bind tighter than + and -
- Left-associative for all binary operators
- Unary minus supported: -3, -(2+1), --3
- Parentheses override precedence
- Raises `ParseError(message: str)` on invalid input:
  - Empty string
  - Unexpected character
  - Mismatched parentheses
  - Incomplete expression (trailing operator, double operator)
- Raises `ZeroDivisionError` on division by zero
- No use of `eval()` or any expression evaluation library
- No imports beyond Python stdlib
