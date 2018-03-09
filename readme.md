# Distributed calculator

This program presents a command line calculator with variables.  There are two interesting features:

1. Variables are stored by formula rather than by value.  If you declare `x = 3` and then `y = x + 1`, then y will be 4.  If you then set `x = 1`, any load from y will return 2.

2. Variables are shared between processes.  If I declare `x = 1` and another person in the same session declares `y = x + 1`, then x will be loaded from my declaration when evaluating y.

## Sessions

When starting the program, you can provide a file with a list of (host, port) tuples.  See session.txt for an exmple.  These network addresses are the other programs that exist on the network.  All hosts must be available before running commands or the behavior is undefined.

If you do not provide a sessions file, all variables will be local.

## Commands


- exit: `exit`: returns nothing and exits the program
- assignment: `<varname> = <expression>`: returns nothing
- evaluate and print a value: `print(<expression>)`: returns nothing
- evaluate and print an expression or value: `<expression>`: returns nothing
- print variable names: `list`: returns nothing
- expressions:
  - `<expression> + <expression>`: returns the result expression
  - `<expression> - <expression>`: returns the result expression
  - `<expression> * <expression>`: returns the result expression
  - `<expression> / <expression>`: returns the result expression (integer division)
  - `<expression> ^ <expression>`: returns the result expression
  - `(<expression>)`: returns the result expression
  - `<integer>`: returns the integer


## Syntax

- variables: `<varname>`: must be lowercase letters a-z
- whitespace is ignored
- everything from `#` to the end of a line is a comment and will be ignored

## Notes

- All variables are integers.  This makes implementation much easier.
- I chose consistency and availability out of CAP.  This is not great for performance, but it is simple and correct.
- I did not consider faults while implementing this.  All programs in the session must be available for this to work.  This makes things a lot easier!

## Implementation notes

1. Each variable has an owner.  The owner is responsible for knowing the latest formula for the variabe.  For simplicity, the owner of a variable cannot change even when the formula is reassigned.  Because each variable has one owner, the variables have consistent formulas.
2. When I declare a variable, wait for other processes to acknowledge the variable before returning.  They must check if they own a variable with the same name.
3. When I evaluate a variable, first check if I own it. Then ask others what it is sequentially.  They will either say "I own that -- here it is" or "I don't own it".  This would be trivial to speed up if this were going into production.
4. It is conceivable for me to declare `x = y + 1`, and then you write `y = x + 1`.  This is disallowed and causes an error because there will be a cycle when calling evaluate.
