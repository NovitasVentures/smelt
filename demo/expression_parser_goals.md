# Expression Parser Test Goals

## Basic arithmetic
- Addition: 1+2 → 3.0
- Subtraction: 5-3 → 2.0
- Multiplication: 3*4 → 12.0
- Division: 10/4 → 2.5

## Operator precedence
- Multiplication before addition: 2+3*4 → 14.0 (not 20.0)
- Division before subtraction: 10-6/2 → 7.0
- Mixed: 2*3+4*5 → 26.0

## Parentheses
- Override precedence: (2+3)*4 → 20.0
- Nested: ((2+3)*4) → 20.0
- Deeply nested: (((1+2))) → 3.0

## Unary minus
- Negative number: -3 → -3.0
- Negative expression: -(2+3) → -5.0
- Double negation: --3 → 3.0
- Unary in expression: 2+-3 → -1.0

## Floats
- Float input: 1.5+2.5 → 4.0
- Float result: 7/2 → 3.5

## Error cases
- Empty string raises ParseError
- Unknown character raises ParseError
- Mismatched parens raises ParseError
- Trailing operator (2+) raises ParseError
- Double operator (2++3) raises ParseError — note: 2+-3 is valid (unary)
- Division by zero raises ZeroDivisionError

## Whitespace
- Spaces ignored: 2 + 3 * 4 → 14.0
- Leading/trailing spaces: " 2+3 " → 5.0
