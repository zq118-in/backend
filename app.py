# -*- coding: utf-8 -*-
# Backend: Flask + SQLite, expression parsing WITHOUT eval
from flask import Flask, request, jsonify, render_template
import sqlite3
import re

app = Flask(__name__)
DB_PATH = 'calculator.db'

# ========== Database init ==========
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS history (
                 id INTEGER PRIMARY KEY AUTOINCREMENT,
                 expr TEXT NOT NULL,
                 result TEXT NOT NULL,
                 create_time TIMESTAMP DEFAULT (datetime('now', 'localtime'))
               )''')
    conn.commit()
    conn.close()

# ========== Expression parser (Shunting-yard, NO eval) ==========
def tokenize(s):
    """Split expression into numbers and operators. Handle unary minus."""
    raw = s.replace(' ', '')
    tokens = []
    i = 0
    n = len(raw)
    if n == 0:
        raise ValueError('Empty expression')
    while i < n:
        ch = raw[i]
        if ch.isdigit() or ch == '.':
            j = i
            while j < n and (raw[j].isdigit() or raw[j] == '.'):
                j += 1
            tokens.append(raw[i:j])
            i = j
        elif ch in '+-*/()':
            if ch == '-' and (i == 0 or raw[i-1] in '+-*/('):
                # unary minus: read the number after it
                j = i + 1
                while j < n and (raw[j].isdigit() or raw[j] == '.'):
                    j += 1
                if j == i + 1:
                    raise ValueError('Invalid expression: bad minus sign')
                tokens.append(raw[i:j])
                i = j
            else:
                tokens.append(ch)
                i += 1
        else:
            raise ValueError('Invalid character: %s' % ch)
    return tokens


def shunting_yard(tokens):
    """Infix -> RPN with operator precedence and parentheses."""
    precedence = {'+': 1, '-': 1, '*': 2, '/': 2}
    output = []
    op_stack = []
    for t in tokens:
        if re.fullmatch(r'-?\d+(\.\d+)?', t):
            output.append(float(t))
        elif t == '(':
            op_stack.append(t)
        elif t == ')':
            while op_stack and op_stack[-1] != '(':
                output.append(op_stack.pop())
            if not op_stack:
                raise ValueError('Mismatched parentheses')
            op_stack.pop()
        else:
            while op_stack and op_stack[-1] != '(' and precedence[op_stack[-1]] >= precedence[t]:
                output.append(op_stack.pop())
            op_stack.append(t)
    while op_stack:
        top = op_stack.pop()
        if top == '(':
            raise ValueError('Mismatched parentheses')
        output.append(top)
    return output


def calc_rpn(rpn):
    """Evaluate RPN expression."""
    stack = []
    for token in rpn:
        if isinstance(token, float):
            stack.append(token)
        else:
            if len(stack) < 2:
                raise ValueError('Invalid expression')
            b = stack.pop()
            a = stack.pop()
            if token == '+':
                stack.append(a + b)
            elif token == '-':
                stack.append(a - b)
            elif token == '*':
                stack.append(a * b)
            elif token == '/':
                if b == 0:
                    raise ZeroDivisionError('Division by zero')
                stack.append(a / b)
    if len(stack) != 1:
        raise ValueError('Invalid expression')
    return stack[0]


def calculate_expression(expr):
    tokens = tokenize(expr)
    rpn = shunting_yard(tokens)
    result = calc_rpn(rpn)
    # clean float output: 2.0 -> 2, limit long decimals
    result = round(result, 10)
    if result == int(result):
        result = int(result)
    return result


# ========== API routes ==========
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/calculate', methods=['POST'])
def api_calculate():
    data = request.get_json(silent=True)
    expr = (data or {}).get('expression', '')
    try:
        result = calculate_expression(expr)
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute('INSERT INTO history (expr, result) VALUES (?, ?)', (expr, str(result)))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'expression': expr, 'result': result})
    except ZeroDivisionError as e:
        return jsonify({'success': False, 'msg': 'Division by zero'}), 400
    except ValueError as e:
        return jsonify({'success': False, 'msg': str(e)}), 400
    except Exception as e:
        return jsonify({'success': False, 'msg': 'Invalid expression'}), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('SELECT id, expr, result, create_time FROM history ORDER BY id DESC')
    rows = cur.fetchall()
    conn.close()
    return jsonify([{'id': r[0], 'expr': r[1], 'result': r[2], 'time': r[3]} for r in rows])


@app.route('/api/history/<int:hid>', methods=['DELETE'])
def delete_history(hid):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM history WHERE id = ?', (hid,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/history', methods=['DELETE'])
def clear_history():
    """Extended feature: clear all history."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute('DELETE FROM history')
    conn.commit()
    conn.close()
    return jsonify({'success': True})


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
