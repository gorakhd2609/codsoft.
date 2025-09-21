# chatbot.py
import re
import json
import os
import datetime
import random
import ast
from responses import greetings, farewell, jokes, facts, help_text, default_response

class UnsafeExpression(Exception):
    pass

class ChatBot:
    def __init__(self, data_file=None, history_limit=200):
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.data_file = data_file or os.path.join(self.base_dir, 'user_data.json')
        self.history_limit = history_limit
        self._load_data()
        self._build_rules()
        self.keyword_intents = {
            'greet': ['hi', 'hello', 'hey', 'hiya', 'good morning', 'good afternoon', 'good evening'],
            'time': ['time', 'what time', 'current time'],
            'joke': ['joke', 'funny'],
            'fact': ['fact', 'fun fact'],
            'help': ['help', 'assist', 'what can you do'],
            'bye': ['bye', 'goodbye', 'see you', 'exit', 'quit'],
            'name_query': ['what is my name', 'who am i', 'my name']
        }

    def _load_data(self):
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except Exception:
                self.data = {'users': {}}
        else:
            self.data = {'users': {}}
            self._save_data()

    def _save_data(self):
        try:
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("Error saving user data:", e)

    def _ensure_user(self, user_name):
        if not user_name:
            user_name = "guest"
        if user_name not in self.data['users']:
            self.data['users'][user_name] = {
                'name': user_name if user_name != "guest" else None,
                'last_seen': None,
                'visits': 0,
                'chats': []
            }
        return user_name

    def _save_chat(self, user_name, sender, text):
        user_name = self._ensure_user(user_name)
        now = datetime.datetime.utcnow().isoformat()
        entry = {'sender': sender, 'text': text, 'time': now}
        chats = self.data['users'][user_name].get('chats', [])
        chats.append(entry)
        # trim history
        if len(chats) > self.history_limit:
            chats = chats[-self.history_limit:]
        self.data['users'][user_name]['chats'] = chats
        self.data['users'][user_name]['last_seen'] = now
        if sender == 'user':
            self.data['users'][user_name]['visits'] = self.data['users'][user_name].get('visits', 0) + 1
        self._save_data()

    def _build_rules(self):
        # rules: (compiled_pattern, handler(match, user_name) -> (reply, new_user_name))
        self.rules = []
        # Set name: "My name is Alice", "I'm Bob", "I am Charlie"
        self.rules.append((re.compile(r"\bmy name is (?P<name>[A-Za-z ]{1,40})\b", re.IGNORECASE), self._set_name))
        self.rules.append((re.compile(r"\bi['’]?m (?P<name>[A-Za-z ]{1,40})\b", re.IGNORECASE), self._set_name))
        self.rules.append((re.compile(r"\bi am (?P<name>[A-Za-z ]{1,40})\b", re.IGNORECASE), self._set_name))
        # Name query
        self.rules.append((re.compile(r"\b(what(\'s| is) my name|who am i)\b", re.IGNORECASE), self._tell_name))
        # Time & date
        self.rules.append((re.compile(r"\b(what time is it|current time|time)\b", re.IGNORECASE), self._tell_time))
        self.rules.append((re.compile(r"\b(what(?:'s| is) the date|date today|what date)\b", re.IGNORECASE), self._tell_date))
        # Joke / fact
        self.rules.append((re.compile(r"\b(joke|tell me a joke)\b", re.IGNORECASE), self._tell_joke))
        self.rules.append((re.compile(r"\b(fact|tell me a fact|fun fact)\b", re.IGNORECASE), self._tell_fact))
        # Calculator: 'calculate 2+2', 'calc 3*4', 'what is 2+2'
        self.rules.append((re.compile(r"\b(?:calculate|calc)\s+(?P<expr>[-+*/().\s0-9]+)$", re.IGNORECASE), self._calculate))
        self.rules.append((re.compile(r"\bwhat(?:'s| is)\s+(?P<expr>[-+*/().\s0-9]+)\??$", re.IGNORECASE), self._calculate))
        # help
        self.rules.append((re.compile(r"\b(help|assist|what can you do)\b", re.IGNORECASE), lambda m, u: (help_text, u)))
        # goodbye
        self.rules.append((re.compile(r"\b(bye|goodbye|see you|exit|quit)\b", re.IGNORECASE), lambda m, u: (random.choice(farewell), u)))

    def _normalize_name(self, raw: str) -> str:
        raw = raw.strip()
        parts = [p.capitalize() for p in raw.split() if p.strip()]
        return " ".join(parts) if parts else None

    def _set_name(self, match, user_name):
        raw = match.group('name')
        name = self._normalize_name(raw)
        if not name:
            return "I didn't catch that name. Try: 'My name is Alice'.", user_name
        user_name = name
        self._ensure_user(user_name)
        reply = f"Nice to meet you, {name}! I'll remember you."
        # store small welcome in history
        self._save_chat(user_name, 'bot', reply)
        return reply, user_name

    def _tell_name(self, match, user_name):
        if user_name and user_name != "guest":
            return f"Your name is {user_name}.", user_name
        return "I don't know your name yet — tell me: 'My name is ...'.", user_name

    def _tell_time(self, match, user_name):
        now = datetime.datetime.now()
        return f"The current time is {now.strftime('%Y-%m-%d %H:%M:%S')}.", user_name

    def _tell_date(self, match, user_name):
        now = datetime.date.today()
        return f"Today's date is {now.isoformat()}.", user_name

    def _tell_joke(self, match, user_name):
        return random.choice(jokes), user_name

    def _tell_fact(self, match, user_name):
        return random.choice(facts), user_name

    # SAFE calculator using AST
    def _safe_eval(self, expr: str):
        # allow digits, whitespace and math operators only
        node = ast.parse(expr, mode='eval')

        allowed_nodes = (ast.Expression, ast.BinOp, ast.UnaryOp, ast.Num, ast.Constant,
                         ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Pow, ast.USub, ast.UAdd,
                         ast.Mod, ast.FloorDiv, ast.Call, ast.Load, ast.Tuple, ast.List,
                         ast.Expr, ast.Subscript, ast.Index)
        # We'll explicitly reject any Name, Attribute, Call (except math functions not allowed), etc.
        for n in ast.walk(node):
            if isinstance(n, ast.Name):
                raise UnsafeExpression("names are not allowed")
            if isinstance(n, ast.Call):
                raise UnsafeExpression("function calls are not allowed")
            if isinstance(n, (ast.Import, ast.ImportFrom, ast.Lambda, ast.Dict)):
                raise UnsafeExpression("disallowed expression")

        # Evaluate only basic arithmetic safely
        compiled = compile(node, '<string>', 'eval')
        return eval(compiled, {"__builtins__": {}})

    def _calculate(self, match, user_name):
        expr = match.groupdict().get('expr', '') if match else ''
        # keep only allowed characters
        expr = expr.strip()
        if not expr:
            return "I couldn't detect an expression to calculate. Try: calculate 2+2", user_name
        try:
            # safe evaluation
            result = self._safe_eval(expr)
            return f"{expr} = {result}", user_name
        except UnsafeExpression:
            return "That's not a safe expression to evaluate. I only do basic arithmetic.", user_name
        except Exception:
            return "I couldn't calculate that. Try a simpler expression like 12 + 3 * (2).", user_name

    def _classify_intent(self, text: str):
        text_lower = text.lower()
        scores = {}
        for intent, keywords in self.keyword_intents.items():
            score = 0
            for kw in keywords:
                if kw in text_lower:
                    score += 1
            scores[intent] = score
        best_intent = max(scores, key=lambda k: scores[k])
        if scores[best_intent] == 0:
            return None
        return best_intent

    def get_response(self, text: str, user_name: str = None):
        text = (text or "").strip()
        if not text:
            return "Please type something.", user_name

        # save user message
        self._save_chat(user_name, 'user', text)

        # 1) rule patterns
        for pattern, handler in self.rules:
            m = pattern.search(text)
            if m:
                try:
                    reply, new_name = handler(m, user_name)
                    # save bot reply
                    self._save_chat(new_name or user_name, 'bot', reply)
                    return reply, new_name or user_name
                except Exception as e:
                    print("Handler error:", e)
                    return "Oops — something went wrong handling that.", user_name

        # 2) fallback: intent classifier
        intent = self._classify_intent(text)
        if intent == 'greet':
            reply = random.choice(greetings)
        elif intent == 'time':
            reply, _ = self._tell_time(None, user_name)
        elif intent == 'joke':
            reply = random.choice(jokes)
        elif intent == 'fact':
            reply = random.choice(facts)
        elif intent == 'help':
            reply = help_text
        elif intent == 'bye':
            reply = random.choice(farewell)
        elif intent == 'name_query':
            reply, _ = self._tell_name(None, user_name)
        else:
            # small keyword responses
            if any(w in text.lower() for w in ['thank', 'thanks']):
                reply = "You're welcome!"
            else:
                reply = default_response

        self._save_chat(user_name, 'bot', reply)
        return reply, user_name

    def get_history(self, user_name: str = None, limit=100):
        if not user_name:
            return []
        if user_name not in self.data['users']:
            return []
        return self.data['users'][user_name].get('chats', [])[-limit:]
