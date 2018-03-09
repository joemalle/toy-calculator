#!/usr/bin/env python
import os
import sys
import time
import threading
from multiprocessing import connection

import argparse
from ply import lex
from ply import yacc
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory


# Global variables
# I know this is ugly but it is very easy

# connections use an authentication key
PROJECT_AUTHKEY = b'Super Secret Key'

# list of hosts in the session
glob_hosts = []

# maps variable names to formulas ... only for locally owned variables
glob_vals = {}

# Lexer

tokens = (
    'EQUALS', 'PLUS', 'MINUS', 'TIMES', 'DIVIDE', 'EXPONENT', 'INTEGER',
    'LPAREN', 'RPAREN', 'VARNAME', 'PRINT', 'LIST', 'EXIT',
)

t_EQUALS    = r'='
t_PLUS      = r'\+'
t_MINUS     = r'-'
t_TIMES     = r'\*'

t_DIVIDE    = r'/'
t_EXPONENT  = r'\^'
t_LPAREN    = r'\('
t_RPAREN    = r'\)'

t_ignore = ' \t\f\r\v'


def t_EXIT(t):
    r'exit'
    return t

def t_PRINT(t):
    r'print'
    return t


def t_LIST(t):
    r'list'
    return t


def t_VARNAME(t):
    r'[a-z]+'
    return t


def t_INTEGER(t):
    r'-?\d+'
    t.value = int(t.value)
    return t


def t_error(t):
    print("Error: Lexer: unable to lex {}".format(t.value[0]))
    raise ValueError

# Parser

def p_exit(p):
    'nothing : EXIT'
    os._exit(0)


def p_assign(p):
    'nothing : VARNAME EQUALS expression'
    evaluate(p[3], set([p[1]]))
    store(p[1], p[3])


def p_calc(p):
    'nothing : expression'
    print(evaluate(p[1]))


def p_print(p):
    'nothing : PRINT expression'
    print(evaluate(p[2], set()))


def p_list(p):
    'nothing : LIST'
    listvars()


def p_expression_plus(p):
    'expression : expression PLUS expression'
    p[0] = ('+', p[1], p[3])


def p_expression_minus(p):
    'expression : expression MINUS expression'
    p[0] = ('-', p[1], p[3])


def p_expression_times(p):
    'expression : expression TIMES expression'
    p[0] = ('*', p[1], p[3])


def p_expression_divide(p):
    'expression : expression DIVIDE expression'
    p[0] = ('/', p[1], p[3])


def p_expression_exponent(p):
    'expression : expression EXPONENT expression'
    p[0] = ('^', p[1], p[3])


def p_expression_integer(p):
    'expression : INTEGER'
    p[0] = ('integer', p[1])


def p_expression_varname(p):
    'expression : VARNAME'
    p[0] = ('varname', p[1])


def p_expression_parens(p):
    'expression : LPAREN expression RPAREN'
    p[0] = p[2]


def p_error(p):
    if p:
        print("Error: Parser: {}".format(p.value))
    else:
        print("Error: Parser: unrecognized line format")
    raise ValueError


precedence = (
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
    ('left', 'RPAREN', 'LPAREN'),
)

# Core functionality

def store(variable, expression):
    global glob_vals
    global glob_hosts
    if variable in glob_vals:
        glob_vals[variable] = expression
    # try to set on all other hosts
    for host in glob_hosts:
        conn = connection.Client(
            host,
            authkey=PROJECT_AUTHKEY,
        )
        conn.send(REQUEST_SET_VALUE(variable, expression))
        reply = conn.recv()
        conn.close()
        if isinstance(reply, I_DONT_KNOW):
            continue
        elif isinstance(reply, ACK):
            return
    # if that fails, set locally
    glob_vals[variable] = expression


def load(variable):
    global glob_vals
    if variable in glob_vals:
        return glob_vals[variable]
    for host in glob_hosts:
        conn = connection.Client(
            host,
            authkey=PROJECT_AUTHKEY,
        )
        conn.send(REQUEST_GET_VALUE(variable))
        reply = conn.recv()
        conn.close()
        if isinstance(reply, I_DONT_KNOW):
            continue
        elif isinstance(reply, RESPONSE_GET_VALUE):
            return reply.value
    print("Error: Interpreter: no variable named {}".format(variable))
    raise ValueError


def evaluate(extuple, so_far=set()):
    expressiontype = extuple[0]
    if expressiontype == "varname":
        if extuple[1] in so_far:
            print("Error: Interpreter: cyclical definition of {}".format(extuple[1]))
            raise ValueError
        so_far.add(extuple[1])
        return evaluate(load(extuple[1]), so_far)
    elif expressiontype == "integer":
        return extuple[1]
    elif expressiontype == "+":
        return evaluate(extuple[1], so_far) + evaluate(extuple[2], so_far)
    elif expressiontype == "-":
        return evaluate(extuple[1], so_far) - evaluate(extuple[2], so_far)
    elif expressiontype == "*":
        return evaluate(extuple[1], so_far) * evaluate(extuple[2], so_far)
    elif expressiontype == "/":
        return evaluate(extuple[1], so_far) / evaluate(extuple[2], so_far)
    elif expressiontype == "^":
        return int(pow(evaluate(extuple[1], so_far), evaluate(extuple[2], so_far)))
    else:
        assert(False)


def listvars():
    global glob_hosts
    if not glob_hosts:
        print "\n".join(sorted(glob_vals.keys()))
        return
    mylist = []
    for host in glob_hosts:
        conn = connection.Client(
            host,
            authkey=PROJECT_AUTHKEY,
        )
        conn.send(REQUEST_LIST())
        reply = conn.recv()
        conn.close()
        mylist.extend(reply.items)
    print("\n".join(sorted(mylist)))
    return


# Protocol

class BASIC_MESSAGE:
    def __init__(self):
        pass

    def __repr__(self):
        return str(self.__dict__)


class ACK(BASIC_MESSAGE):
    def __init__(self):
        BASIC_MESSAGE.__init__(self)


class I_DONT_KNOW(BASIC_MESSAGE):
    def __init__(self):
        BASIC_MESSAGE.__init__(self)


class REQUEST_GET_VALUE(BASIC_MESSAGE):
    def __init__(self, varname):
        BASIC_MESSAGE.__init__(self)
        self.varname = varname


class REQUEST_SET_VALUE(BASIC_MESSAGE):
    def __init__(self, varname, value):
        BASIC_MESSAGE.__init__(self)
        self.varname = varname
        self.value = value

class REQUEST_LIST(BASIC_MESSAGE):
    def __init__(self):
        BASIC_MESSAGE.__init__(self)


class RESPONSE_GET_VALUE(BASIC_MESSAGE):
    def __init__(self, varname, value):
        BASIC_MESSAGE.__init__(self)
        self.varname = varname
        self.value = value

class RESPONSE_LIST(BASIC_MESSAGE):
    def __init__(self, items):
        BASIC_MESSAGE.__init__(self)
        self.items = items


# Networking

def server():
    global glob_hosts
    global glob_vals
    serversocket = None
    for host in glob_hosts:
        try:
            serversocket = connection.Listener(
                host,
                authkey=PROJECT_AUTHKEY,
            )
        except:
            continue
    if not serversocket:
        print("Error: Network: couldn't connect")
        os._exit(1)
    print("Connected")
    while True:
        clientsocket = serversocket.accept()
        request = clientsocket.recv()
        if isinstance(request, REQUEST_GET_VALUE):
            if request.varname in glob_vals:
                clientsocket.send(RESPONSE_GET_VALUE(request.varname, glob_vals[request.varname]))
            else:
                clientsocket.send(I_DONT_KNOW())
        elif isinstance(request, REQUEST_SET_VALUE):
            if request.varname in glob_vals:
                glob_vals[request.varname] = request.value
                clientsocket.send(ACK())
            else:
                clientsocket.send(I_DONT_KNOW())
        elif isinstance(request, REQUEST_LIST):
            clientsocket.send(RESPONSE_LIST(glob_vals.keys()))
        clientsocket.close()
    serversocket.close()

# Command line

def processcommandline():
    global glob_hosts
    parser = argparse.ArgumentParser(
        description="A calculator with a few tricks"
    )
    parser.add_argument(
        'hosts',
        metavar='N',
        type=argparse.FileType("rb"),
        default=None,
        nargs='?',
        help='a hosts file with (host, port) on each line'
    )
    parser.add_argument(
        "-t", "--test",
        dest="test",
        help="expects a file from which to read input",
        type=argparse.FileType("rb"),
        default=None,
        nargs='?',
    )
    args = parser.parse_args()
    if args.hosts:
        glob_hosts = [eval(x.strip()) for x in args.hosts.readlines()]
    if not args.test:
        return None
    return [x.strip() for x in args.test.readlines()]


# Script

lexer = lex.lex()


def process(line):
    line = line.split('#')[0]
    if not line:
        return
    try:
        parser.parse(line)
    except ValueError:
        pass


if __name__ == "__main__":
    parser = yacc.yacc()
    testlines = processcommandline()
    if glob_hosts:
        threading.Thread(target=server).start()
        time.sleep(1)
    if testlines:
        for line in testlines:
            process(line)
        os._exit(0)
    while True:
       try:
           user_input = prompt(u'> ', history=FileHistory('history.txt'),)
       except:
           os._exit(0)
       process(user_input)
