import sys
import os
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QListWidget,
    QTextEdit,
)
from PyQt6.QtGui import QFont
import sqlite3
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
from PyQt6.QtWebEngineWidgets import QWebEngineView
from pathlib import Path
from typing import Generator
import openai
import asyncio
from qasync import QEventLoop, asyncSlot
import time


class CodeHighlighter:
    def __init__(self):
        self.formatter = HtmlFormatter()

    def pre_process_text(self, text: str) -> Generator:
        """ """
        lines = text.splitlines()
        code_in = False
        code = str()
        lang = str()

        """
        What happen if reguest is incomplete? 
        """
        for line in lines:
            if line.startswith("```"):
                # Can be code start, and and
                if code_in:
                    # In this case finished cove
                    code_in = False
                    yield ((lang, code))
                    code = ""
                else:
                    # New code block
                    if len(line) == 3:
                        # MD
                        lang = "Markdown"
                        code_in = True
                    else:
                        # Others
                        lang = line[3:]
                        code_in = True
            else:
                if code_in:
                    code = code + line + "\n"
                else:
                    yield (("none", line))

    def get_styes(self, file_path) -> None:
        # In Case
        with open(file_path, "w") as out_file:
            out_file.write(HtmlFormatter().get_style_defs(".highlight"))

    def process_text(self, text: str) -> str:
        result = str()

        for text_type, text_content in self.pre_process_text(text):
            if text_type == "none":
                result += f"<p>{text_content}</p>"
            else:
                try:
                    lexer = get_lexer_by_name(text_type, stripall=True)
                    formatter = HtmlFormatter(linenos=True, cssclass="highlight")
                    result += f"<code class='code'>\n<div class='source'>{text_type}:</div>\n {highlight(text_content, lexer, formatter)}\n </code>\n"
                except Exception as e:
                    print(f"Missing lexer {str(e)}")
                    result += f"<pre><code class='code'>{text_content}</code></pre>"
        return result


class MyWindow(QMainWindow):
    def __init__(self):
        self.cwd = Path.cwd()

        super().__init__()

        self.init_db("catgpt.db")

        self.initUI()

        self.highlighter = CodeHighlighter()

        self.current_thread = None

    def init_db(self, db_file: str) -> None:
        """
        expected tables: "settings", "chatLog", "appLog"
        """

        self.con = sqlite3.connect(db_file)
        self.cursor = self.con.cursor()

        # check if all required tables exits. I there is any error whe have to re inicailase our db.
        self.cursor.execute(
            """SELECT
                CASE
                    WHEN (
                        SELECT COUNT(*) FROM sqlite_master
                        WHERE type='table' AND name IN ('setting', 'chatlog', 'applog')
                    ) = 3 THEN 'true'
                    ELSE 'false'
                END AS all_tables_exist;"""
        )

        if self.cursor.fetchone()[0].lower() == "false":
            try:
                with open("sql_queries.sql", "r") as query_file:
                    print("Restarting and recreating tables...")
                    queries = query_file.read()
                    self.cursor.executescript(queries)
            except (sqlite3.Error, IOError) as e:
                print(f"Error: {e}")
                self.con.close()

    def initUI(self):
        self.setWindowTitle("ChatGPT")
        self.setGeometry(100, 100, 1024, 600)

        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)
        sansFont = QFont("Helvetica", 12)

        main_widget.setFont(sansFont)

        layout = QHBoxLayout()
        main_widget.setLayout(layout)

        left_col_layout = QVBoxLayout()
        right_col_layout = QVBoxLayout()

        # Left Column
        new_chat = QPushButton("Create", objectName="createButton")
        # new_chat.setStyleSheet(u"background-color: rgb(32, 33, 35);color:#fff;border-color: rgb(255, 255, 255);")
        left_col_layout.addWidget(new_chat)
        list_widget = QListWidget()
        # list_widget.setStyleSheet(u"background-color: rgb(32, 33, 35);color:#fff")
        list_widget.addItems(["Input Field Height", "Using asyncio with PyQt5"])
        left_col_layout.addWidget(list_widget)

        # Right Column
        # right_col_layout.addWidget(QLabel("Info Banner"))
        self.multi_line_list = QWebEngineView()
        self.multi_line_list.setFont(sansFont)
        # multi_line_list.setStyleSheet(u"background-color: rgb(32, 33, 35);color:#fff")

        #
        template = Path(self.cwd, "templates", "base.html").read_text()
        css = Path(self.cwd, "css", "base.css").read_text()

        template_with_css = template.replace("__style__", css)

        full_text = template_with_css

        # END TMP CODE

        with open("current_html.html", "w") as out_file:
            out_file.write(full_text)

        self.multi_line_list.setHtml(full_text)

        right_col_layout.addWidget(self.multi_line_list)

        self.input_field = QTextEdit()
        self.input_field.setFixedHeight(60)
        # input_field.setStyleSheet(u"background-color: rgb(64, 65, 79); color: rgb(255, 255, 255);")

        send_button = QPushButton("Send", objectName="sendButton")
        send_button.clicked.connect(self.coverstateton)
        # send_button.setStyleSheet(u"background-color: rgb(32, 33, 35);color:#fff;border-color: rgb(255, 255, 255);")
        right_col_layout.addWidget(self.input_field)
        right_col_layout.addWidget(send_button)

        layout.addLayout(left_col_layout, 20)
        layout.addLayout(right_col_layout, 80)

    def append_msg(self, role: str, msg: str):
        formatted_response_js = msg.replace(
            "'", "\\'"
        )  # Escape single quotes for JavaScript
        formatted_response_js = formatted_response_js.replace(
            "\n", "\\n"
        )  # Escape newline characters

        js_code = f"""
        var newDiv = document.createElement('div');
        newDiv.className = '{role}';
        newDiv.innerHTML = '{formatted_response_js}';
        document.body.appendChild(newDiv);
        """

        self.multi_line_list.page().runJavaScript(js_code)

    @asyncSlot()
    async def coverstateton(self):
        # api_response = """Certainly! Here's a Python example of list comprehension that gets the squares of numbers from 1 to 10:\n\n```python\nsquares = [x**2 for x in range(1, 11)]\nprint(squares)\nn='kutya'\n```\n\nThe output will be `[1, 4, 9, 16, 25, 36, 49, 64, 81, 100]`. Now you have a list of square numbers in just one line of code!"""
        # api_response = """Sure! Here's a short example of a text in Markdown language:\n\n```\n# Welcome to Markdown!\n\nMarkdown is a lightweight markup language that allows you to style and format youteted with Markdown, all you need is a simple text editor. Write your content using Markdown syntax, save with a .md file extension, and you're ready to rock!\n\nHappy Markdown-ing!\n```\n\nHope that helps you get started with Markdown! If you have any questions or need further assistance, feel free to ask!"""
        question = self.input_field.toPlainText()
        self.input_field.clear()
        self.append_msg("group_user", question)
        
        # find out is it a actual thread.
        if self.current_thread is not None :
            response = await self.chat_with_openai(question, self.current_thread)
        else:
            response = await self.chat_with_openai(question)
            self.current_thread = response[0]
            
        ch = CodeHighlighter()
        formatted_response = ch.process_text(response[1])

        self.append_msg("group_assistant", formatted_response)


        data = [
            (None, self.current_thread, "user", question),
            (None, self.current_thread, "assistant", response[1]),
        ]
        self.cursor.executemany(
            "INSERT INTO chatlog VALUES(?,CURRENT_TIMESTAMP,?, ?, ?)", data
        )
        self.con.commit()

    async def chat_with_openai(self, prompt, id=None):
        messages = [
            {
                "role": "system",
                "content": "You are a scientific advisor. You are talking with a geek programmer who loves smartass jokes!",
            },
        ]
        
        if id is not None:
            print('id is not None')
            params = (id,)
            res = self.cursor.execute("SELECT role,content FROM chatlog WHERE thread_id = ?", params)
            additional_list_items=[{'role':r,'content':c} for r,c in res.fetchall() ]
            messages = messages + additional_list_items
            
        messages.append({"role": "user", "content": prompt})


        print(messages)
            
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.call_openai, messages)

        return (response["id"], response["choices"][0]["message"]["content"])

    def call_openai(self, messages):
        return openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            # model="gpt-4",
            messages=messages,
            max_tokens=1024,
        )

    def _coverstateton(self):
        """
        Protocol:
        For the first interaction in a thread:
        - Initial question from the user. (Token count: "prompt_tokens")
        - Response from OpenAI with an associated ID ("CHATGPT_ID"). (Token count: "completion_tokens")

        For subsequent interactions in the same conversation thread:
        - Use the provided CHATGPT_ID and include all accumulated previous messages (user and assistant) up to the model's token limit.
          Be mindful of token usage for every message.

        Note:
        - The "prompt_tokens" indicate the tokens used in the initial question.
        - The "completion_tokens" indicate the tokens used in OpenAI's response.
        - The total token count for continuation includes tokens in all previous messages and assistant responses,
          taking into account token limits.
        - Include information that the response content contains text and a unique ID, where the ID type is text.
        - Keep in mind that every step adds to the cumulative token usage, doubling with each new message, leading to increased cost.
        """
        api_response = """Certainly! Here's a Python example of list comprehension that gets the squares of numbers from 1 to 10:\n\n```python\nsquares = [x**2 for x in range(1, 11)]\nprint(squares)\nn='kutya'\n```\n\nThe output will be `[1, 4, 9, 16, 25, 36, 49, 64, 81, 100]`. Now you have a list of square numbers in just one line of code!"""
        # Markdown Introduction

        api_response = """Markdown is a lightweight markup language that's easy to read and write. It's widely used for formatting plain text, especially for creating documents, web pages, and README files.

Some of its key features include:

- **Simplicity**: Markdown uses simple and intuitive syntax, making it accessible to beginners.
- **Readability**: Markdown documents are easy to read, even in their plain text form.
- **Versatility**: Markdown supports a wide range of formatting options, including headings, lists, links, and images.

## Getting Started

To get started with Markdown, all you need is a text editor. You can format your text using a few basic symbols and conventions. For example:

- To create a heading, use `#` followed by a space and your heading text.
- To create a list, use `-` or `*` followed by a space.
- To create links, enclose the link text in square brackets `[ ]` and the URL in parentheses `( )`.

Markdown is a powerful tool for quickly and easily formatting text. Give it a try!"""

        ch = CodeHighlighter()
        formatted_response = ch.process_text(api_response)

        print(formatted_response)

        self.multi_line_list.page().runJavaScript(
            f"""var newDiv = document.createElement('div');
newDiv.className = 'group_assistant';
newDiv.innerHTML = '{formatted_response}';
document.body.appendChild(newDiv);"""
        )

        '''self.multi_line_list.page().runJavaScript(f"""var newDiv = document.createElement('div');
        newDiv.className = 'group_user';
        newDiv.innerHTML = '{content}';
        document.body.appendChild(newDiv);""")'''


def main():
    # cmd>set OPENAI_API_KEY=

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    window = MyWindow()
    window.show()

    with loop:
        sys.exit(loop.run_forever())
        # sys.exit(app.exec())


if __name__ == "__main__":
    # by openai recommendation
    openai.api_key = os.getenv("OPENAI_API_KEY")
    main()


""" -------------------------------------------------------
https://doc.qt.io/qtforpython-6/examples/example_async_minimal.html
https://docs.python.org/3/library/sqlite3.html

"""
