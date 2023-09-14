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
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QStyleFactory,
    QSizePolicy
)
from PyQt6.QtGui import QFont, QAction
from PyQt6.QtCore import Qt, QTimer, pyqtSlot
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
import json




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
    def __init__(self, debug: bool=False):
        self.cwd = Path.cwd()
        self.debug = debug
        super().__init__()

        self.init_db("catgpt.sqlite3")
        self.reset_chat()
        self.initUI()
        # check Config
        with open("config.json", "r") as config_file:
            content = config_file.read()
            config_content = json.loads(content)

            # expected keys:
            expected_keys = ["model", "max_tokens"]

            # by openai recommendation
            key = os.getenv("OPENAI_API_KEY")
            if key is None:
                raise Exception("Missing OPENAI_API_KEY")
            else:
                openai.api_key = key

            if all(key in config_content for key in expected_keys):
                #
                if "system_role_content" in config_content.keys():
                    self.system_role_content = config_content.pop("system_role_content")
                else:
                    self.system_role_content = None

                self.chatGPT_setting = {
                    "model": config_content.pop("model"),
                    "max_tokens": config_content.pop("max_tokens"),
                }
                info = f"model {self.chatGPT_setting['model']} | max_tokens: {self.chatGPT_setting['max_tokens']}"
                self.label.setText(info)
                for item in config_content:
                    self.chatGPT_setting[item] = config_content[item]
            else:
                raise Exception(
                    f"Missing key(s) {list(set(config_content.keys()) & set(expected_keys))}"
                )

            print(self.chatGPT_setting)

        self.highlighter = CodeHighlighter()

        self.current_chat_gpt_id = None

        # restore some things:
        #
        self.cursor.execute("SELECT title from thread where 1")

        self.list_widget.addItems([t[0] for t in self.cursor.fetchall()])

    def init_db(self, db_file: str) -> None:
        """
        expected tables: "thread", "chatLog", ""
        """

        self.con = sqlite3.connect(db_file)
        self.cursor = self.con.cursor()

        # check if all required tables exits. I there is any error whe have to re inicailase our db.
        self.cursor.execute(
            """SELECT
                CASE
                    WHEN (
                        SELECT COUNT(*) FROM sqlite_master
                        WHERE type='table' AND name IN ('thread', 'chatlog')
                    ) = 2 THEN 'true'
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
        self.setGeometry(100, 100, 1024, 960)

        self.main_widget = QWidget(self)
        self.setCentralWidget(self.main_widget)
        sansFont = QFont("Helvetica", 12)

        self.main_widget.setFont(sansFont)
        
        

        layout = QHBoxLayout()
        self.main_widget.setLayout(layout)

        left_col_layout = QVBoxLayout()
        right_col_layout = QVBoxLayout()

        # --------------------------------------------------------------------
        # Left Column

        label = QLabel("Saved Chats")
        left_col_layout.addWidget(label)

        self.list_widget = QListWidget()

        self.list_widget.itemDoubleClicked.connect(self.list_double_click)

        # Menu for list_widget
        self.deleteMenu = QMenu()
        self.deleteAction = QAction("Delete", left_col_layout)
        self.deleteAction.triggered.connect(self.list_onDelete)
        self.deleteMenu.addAction(self.deleteAction)
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(
            self.customContextMenuRequested
        )

        left_col_layout.addWidget(self.list_widget)

        # --------------------------------------------------------------------
        # Right Column

        self.label = QLabel("Info")
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_col_layout.addWidget(self.label)

        inline_layout = QHBoxLayout()

        label = QLabel("Thread name:")
        inline_layout.addWidget(label)

        # Add a text input (single line)
        self.save_input = QLineEdit()
        inline_layout.addWidget(self.save_input)

        # Add a save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)

        inline_layout.addWidget(save_button)

        # Add a reset button
        reset_button = QPushButton("Reset")
        reset_button.clicked.connect(self.reset)
        reset_button.setStyleSheet("color:yellow;")
        inline_layout.addWidget(reset_button)

        inline_layout.addSpacing(10)
        
        if self.debug:
            dump_button = QPushButton("Dump")
            dump_button.clicked.connect(self.dump_html)
            inline_layout.addWidget(dump_button)
            inline_layout.addSpacing(10)

        # Add a Quit button
        quit_button = QPushButton("Quit")
        quit_button.clicked.connect(self.quit)
        inline_layout.addWidget(quit_button)

        right_col_layout.addLayout(inline_layout)
        self.web_engine_view = QWebEngineView()
        self.web_engine_view.setFont(sansFont)
        self.web_engine_view.setZoomFactor(1.0) 
        
        self.web_engine_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
      
       
        
        self.web_engine_view.page().profile().clearHttpCache()
        
        

        template = Path(self.cwd, "templates", "base.html").read_text()
        css = Path(self.cwd, "css", "base.css").read_text()

        template_with_css = template.replace("__style__", css)

        self.full_text = template_with_css

        # END TMP CODE

        # For debug
        """with open("current_html.html", "w") as out_file:
            out_file.write(self.full_text)"""

        self.web_engine_view.setHtml(self.full_text)

        right_col_layout.addWidget(self.web_engine_view,1)

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
        
        
    
    @pyqtSlot(str)
    def write_dump(self, content):
        file_path = "webpage.html"
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(content)
            print(f"HTML content saved to {file_path}")
    
    def dump_html(self):
        self.web_engine_view.page().runJavaScript("document.documentElement.outerHTML;", self.write_dump)
    
    def list_onDelete(self):
        reply = QMessageBox.question(
            self, "Confirmation", "Are you sure you want to proceed?"
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            selectedItems = self.list_widget.selectedItems()

            # Remove the selected items from the list widget
            for item in selectedItems:
                self.list_widget.takeItem(self.list_widget.row(item))
                self.reset_chat(item.text())

            self.reset()

    def customContextMenuRequested(self, pos):
        # Get the item at the clicked position
        item = self.list_widget.itemAt(pos)

        # If the item is not None, show the context menu
        if item:
            self.deleteMenu.exec(self.list_widget.mapToGlobal(pos))

    def list_double_click(self, item) -> None:
        if self.current_chat_gpt_id is not None:
            self.reset()
        self.load_conversation(item)

    def load_conversation(self, item) -> None:
        res = self.cursor.execute(
            "select id,chat_gpt_id from thread where title = ?", (item.text(),)
        )

        id, self.current_chat_gpt_id = res.fetchone()

        res = self.cursor.execute(
            "select role,content from chatlog where thread_id = ?", (id,)
        )

        ch = CodeHighlighter()
        for role, content in res.fetchall():
            if role == "user":
                self.append_msg("group_user", content.strip())
            elif role == "assistant":
                formatted_response = ch.process_text(content.strip())
                self.append_msg("group_assistant", formatted_response)

        print("load_conversation", self.current_chat_gpt_id)
        
        #I had a problem with the text display, but even if I resize the window just a little bit, it gets fixed.
        current_width = self.width()
        current_height = self.height()
        
        self.resize(current_width, current_height+1)
        

        
    def save(self) -> None:
        """
        Save current thread to database and add to list
        """
        title = self.save_input.text()

        if title.strip() == "":
            QMessageBox.warning(self, "Warning", "Empty Value")
            return

        res = self.cursor.execute(
            "SELECT count(*) from thread WHERE title = ?", (title,)
        )

        if res.fetchone()[0] != 0:
            QMessageBox.warning(self, "Warning", "Name must be unique")
            return

        reply = QMessageBox.question(
            self, "Confirmation", "Are you sure you want to proceed?"
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.cursor.execute(
                    "UPDATE thread SET title = ? WHERE chat_gpt_id = ?",
                    (title, self.current_chat_gpt_id),
                )
                self.con.commit()
            except Exception as e:
                print(e)
                self.con.set_trace_callback(print)

            self.list_widget.addItem(title)

    def reset(self) -> None:
      
        try:
            js_code = "var body = document.body;while (body.firstChild) { body.removeChild(body.firstChild);}"
            self.web_engine_view.page().runJavaScript(js_code)

            self.current_chat_gpt_id = None
            self.reset_chat()
            print("reset")

        except Exception as e:
            print(f"error: {e}")

    def reset_chat(self, name: str = "current") -> None:
        """
        We need three  times
        1. When start the program and clean the dafault
        2. When used reset button
        3. When load a new chat
        """
        try:
            # check if thread exits
            res = self.cursor.execute("SELECT id FROM thread WHERE title = ?", (name,))
            self.con.commit()
            thread_id_tmp = res.fetchone()
            if thread_id_tmp:
                print(thread_id_tmp[0])
                self.cursor.execute(
                    "DELETE FROM chatlog WHERE thread_id = ? ", (thread_id_tmp[0],)
                )
                self.cursor.execute(
                    "DELETE FROM thread WHERE id = ? ", (thread_id_tmp[0],)
                )
                self.con.commit()

        except Exception as e:
            print(f"error: {e}")

    def quit(self):
        QApplication.quit()

    def append_msg(self, role: str, msg: str) -> None:
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
        self.web_engine_view.page().runJavaScript(js_code)

    @asyncSlot()
    async def coverstateton(self) -> None:
        """_summary_"""
        is_new_thread = True
        question = self.input_field.toPlainText()
        self.input_field.clear()
        self.append_msg("group_user", question.strip())

        # find out is it a actual thread. If don't we will use a defaul "no name" tthread
        if self.current_chat_gpt_id is not None:
            response = await self.chat_with_openai(question, self.current_chat_gpt_id)
            is_new_thread = False
        else:
            response = await self.chat_with_openai(question)
            # Open a new thread
            is_new_thread = True
            self.current_chat_gpt_id = response[0]

        ch = CodeHighlighter()
        formatted_response = ch.process_text(response[1].strip())

        self.append_msg("group_assistant", formatted_response)

        # save tp database.

        # check if thread exits
        res = self.cursor.execute(
            "SELECT id FROM thread WHERE chat_gpt_id = ?", (self.current_chat_gpt_id,)
        )

        thread_id_tmp = res.fetchone()
        if thread_id_tmp:
            thread_id = thread_id_tmp[0]
        else:
            # If not thred id it's a new thread so the None
            self.cursor.execute(
                "INSERT INTO thread VALUES(?,?,?)",
                (None, self.current_chat_gpt_id, "current"),
            )
            self.con.commit()
            thread_id = self.cursor.lastrowid

        print(thread_id)
        data = [
            (None, thread_id, "user", question),
            (None, thread_id, "assistant", response[1]),
        ]
        self.cursor.executemany(
            "INSERT INTO chatlog VALUES(?,CURRENT_TIMESTAMP,?, ?, ?)", data
        )
        self.con.commit()

    async def chat_with_openai(self, prompt: str, id: str = None) -> tuple:
        messages = []
        if self.system_role_content:
            messages.append({"role": "system", "content": str(self.system_role_content)})

        if id is not None:
            # In case if there are history.
            res = self.cursor.execute(
                "SELECT role,content FROM chatlog WHERE thread_id = ?", (id,)
            )
            additional_list_items = [
                {"role": r, "content": c} for r, c in res.fetchall()
            ]
            messages = messages + additional_list_items

        messages.append({"role": "user", "content": prompt})

        print(messages)

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, self.call_openai, messages)

        return (response["id"], response["choices"][0]["message"]["content"])

    def call_openai(self, messages):
        setting = self.chatGPT_setting.copy()
        setting["messages"] = messages

        return openai.ChatCompletion.create(**setting)

    def _coverstateton(self):
        ch = CodeHighlighter()
        formatted_response = ch.process_text(api_response)

        print(formatted_response)

        self.web_engine_view.page().runJavaScript(
            f"""var newDiv = document.createElement('div');
newDiv.className = 'group_assistant';
newDiv.innerHTML = '{formatted_response}';
document.body.appendChild(newDiv);"""
        )

        '''self.web_engine_view.page().runJavaScript(f"""var newDiv = document.createElement('div');
        newDiv.className = 'group_user';
        newDiv.innerHTML = '{content}';
        document.body.appendChild(newDiv);""")'''


def main():
    # cmd>set OPENAI_API_KEY=

    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)

    try:
        window = MyWindow(True)
    except FileNotFoundError as e:
        print(f"Error: {e}. Make sure 'config.json' exists.")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        sys.exit(1)

    window.show()

    with loop:
        sys.exit(loop.run_forever())


if __name__ == "__main__":
    main()


""" -------------------------------------------------------
https://doc.qt.io/qtforpython-6/examples/example_async_minimal.html
https://docs.python.org/3/library/sqlite3.html

Worker?
https://stackoverflow.com/questions/72693388/update-html-content-in-qwebengineview

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
