import os, io
import json
import pandas as pd
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
from flask import Flask, request, jsonify, make_response

client = OpenAI()

load_dotenv()
app = Flask(__name__)

@app.route('/api/init-assistant', methods=['POST'])
def initAssistant():
    """
    Initialize a new Financial Assistant using OpenAI's beta API.
    """
    try:
        # requestData = request.get_json()
        assistant = client.beta.assistants.create(
        name='Financial Assistant',
        instructions="""
        You are a financial assistant. You are expected to answer questions based on the provided financial data. The user will ask you to answer questions in these possible formats: Simple Response (String), Excel file, table. Responses should be given in one of three formats: string, table, or excel. 
        Always default to the string format unless the user specifies a different format in the message.
        You will only provide the response in the requested format. For each format, the response should be structured as follows:
        For the string format, the JSON structure should be:
        {
        "response_type": "string",
        "data": {
        "comments": "Any additional comments or remarks."
        },
        }
        For the excel format, always return the data, never return any file path or anything. The JSON structure should be:
        {
        "status": "success",
        "response_type": "excel",
        "data": {
        "headers": ["Question", "Answer", "Total Revenue", "Expenses", "Profit", "Comments"],
        "rows": [
        ["Your question here", "The answer here", "Total revenue value", "Expenses value", "Profit value", "Any additional comments"]
        ]
        },
        }
        For the table format, the JSON structure should be:
        {
        "status": "success",
        "response_type": "table",
        "data": {
        "headers": ["Question", "Answer", "Total Revenue", "Expenses", "Profit", "Comments"],
        "rows": [
        ["Your question here", "The answer here", "Total revenue value", "Expenses value", "Profit value", "Any additional comments"]
        ]
        },
        }
        You will answer only in the specified format (string, table, or excel) and include the "response_type" attribute in the response to indicate the format used. The headers in excel file and table are just given as an example for you to understand. So, they need to be adjusted according to the financial data headers provided to you later in this conversation. So, use them as headers for both excel and table. Do not provide all formats in one response; answer based on the type requested. Financial data will be provided in a through JSON. The answers should reflect this data.
        If user asks you to return a file or anything, just return the data in the format specified above, and the user will handle the rest. DO NOT return any file path EVER.
        """,
        model='gpt-4o-mini'
        )
        return jsonify({"assistantId": assistant.id}), 200
    except Exception as error:
        app.logger.error(f'Error initializing assistant: {str(error)}')
        return 'Failed to create assistant', 500

@app.route('/api/init-thread', methods=['POST'])
def initThread():
    """
    Initialize a new thread for the assistant.
    """
    try:
        thread = client.beta.threads.create()
        return jsonify({"threadId": thread.id}), 200
    except Exception as error:
        app.logger.error(f'Error initializing thread: {str(error)}')
        return 'Failed to create thread', 500

# @app.route('/api/list-files', methods=['GET'])
# def list_files():
#     """
#     List all files uploaded to the assistant.
#     """
#     files_data = []
#     try:
#         files = client.files.list()
#         for file in files.data:
#             files_data.append({"fileId": file.id, "fileName": file.filename, "fileBytes": file.bytes})
#         return jsonify({"filesData": files_data}), 200
#     except Exception as error:
#         app.logger.error(f'Error listing files: {str(error)}')
#         return 'Failed to list files', 500


@app.route('/api/list-messages', methods=['POST'])
def list_messages():
    """
    List all messages in a specific thread.
    """
    message_data = []
    thread_id = request.get_json()['threadId']
    messages = list(client.beta.threads.messages.list(thread_id=thread_id, run_id=""))
    for message in messages:
        message_data.append({"role": message.role, "content": message.content[0].text.value})
    return jsonify({"messages": message_data}), 200

@app.route('/api/feed-data', methods=['POST'])
def feed_data():
    """
    Feed financial data from an Excel file to the assistant within a specific thread.
    """

    thread_id = request.form.get('threadId')
    if not thread_id:
        return jsonify({"message":'threadId is required'}), 400
    
    file = request.files['file']
    if not file:
        return jsonify({"message":'Excel file is required'}), 400
    
    # Read the Excel file
    df = pd.read_excel(file)

    print("Dataframe: ", df)
    
    # Convert DataFrame to JSON with row numbers starting from 1
    df.reset_index(inplace=True)
    df.rename(columns={'index': 'row_number'}, inplace=True)
    df['row_number'] += 1  # Increment row_number to start from 1
    data_json = df.to_dict(orient='records')
    
    # Define maximum number of rows per chunk (adjust as needed)
    MAX_ROWS_PER_CHUNK = 30  # number of rows
    
    # Split the data into chunks while maintaining structure
    chunks = []
    for i in range(0, len(data_json), MAX_ROWS_PER_CHUNK):
        chunk = {
            "columns": df.columns.tolist(),
            "rows": data_json[i:i + MAX_ROWS_PER_CHUNK]
        }
        chunks.append(chunk)
    
    counter = 1

    # Attach each chunk to the thread as JSON
    for chunk in chunks:
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=f"\n{(chunk)}"
        )
        counter += 1
        
        print(f"Successfully uploaded {counter} out of {len(chunks)} chunks to thread {thread_id}.")
    
    return jsonify({"message": "Data uploaded successfully."}), 200


@app.route('/api/get-response', methods=['POST'])
def getResponse():
    """
    Get the assistant's response to a user's question within a specific thread.
    """

    data = request.get_json()
    threadId = data.get('threadId')
    assistantId = data.get('assistantId')
    question = data.get('question')
    
    if not threadId or not assistantId or not question:
        return 'threadId, assistantId, and question are required', 400
    
    client.beta.threads.messages.create(
    thread_id=threadId,
    role='user',
    content=question
    )
    runResponse = client.beta.threads.runs.create_and_poll(
    thread_id=threadId,
    assistant_id=assistantId,
    temperature=0.1
    )
    if runResponse.status == 'completed':
        messages = client.beta.threads.messages.list(runResponse.thread_id)
        for message in messages.data:
            if message.role == 'assistant':
                response_content = message.content[0].text.value
                break
        jsonData = json.loads(response_content)
        if jsonData['response_type'] == 'string' or jsonData['response_type'] == 'table':
            return jsonData, 200

        elif jsonData['response_type'] == 'excel':
            io_buffer = io.BytesIO()
            df = pd.DataFrame(jsonData['data']['rows'], columns=jsonData['data']['headers'])
            df.to_excel(io_buffer, index=False)
            xlsx_data = io_buffer.getvalue()
            response = make_response(xlsx_data)
            cd = f'attachment; filename=data.xlsx'
            response.headers['Content-Disposition'] = cd
            response.mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            return response

        return response_content, 200
    else:
        return jsonify({"response": "Response is still processing."}), 202

    
if __name__ == 'main':
    port = int(os.getenv('PORT', 8080))
    app.run(host='0.0.0.0', port=port)