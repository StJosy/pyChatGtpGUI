**Project Name**: ChatGPT Python GUI

**Description**:

This project is a PyQt6-based chat application integrated with OpenAI's GPT models, and it allows users to configure the model's behavior using a JSON configuration file. The application provides a user-friendly chat interface where users can input questions or messages, and the assistant responds accordingly. The configuration file allows customization of various GPT model parameters, such as model selection, token limits, temperature, and more.

**Features**:

- PyQt6-based graphical user interface.
- Integration with OpenAI's GPT models.
- Customizable GPT model behavior through a JSON configuration file.
- Syntax highlighting for code snippets in the responses using Pygments.
- SQLite database for storing chat logs.
- Markdown rendering for explanations and information.
- Basic HTML templating for styling.

**Usage**:

1. Users can input their queries or messages in the text field.
2. The application communicates with the selected GPT model based on the provided configuration.
3. Responses are displayed in the right column with syntax-highlighted code snippets where relevant.
4. Chat logs are stored in an SQLite database for reference.
5. Users can modify the GPT model's behavior by editing the configuration JSON file.

**Configuration JSON Example**:

```json
{
    "model": "gpt-3.5-turbo",
    "max_tokens": 256,
    "temperature": 0.5,
    "top_p": 1,
    "frequency_penalty": 0,
    "presence_penalty": 0,
    "system_role_content": "You are a scientific advisor. You are talking with a geek programmer who loves smartass jokes!"
}
```
**Installation**:
```bash
pip install PyQt6 pygments openai qasync PyQtWebEngine
```

**Run**:
You have to set OPENAI_API_KEY  like:
```bash
set OPENAI_API_KEY=your_secret key
```
OR
```bash
export OPENAI_API_KEY=your_secret key
```
 



**License**:

This project is open-source and is available under the MIT License.

**Contributors**:

Currently developed and maintained by a single developer.

