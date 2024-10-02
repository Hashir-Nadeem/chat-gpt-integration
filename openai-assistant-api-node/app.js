const express = require('express');
const OpenAI = require('openai');
const bodyParser = require('body-parser');
const app = express();
app.use(bodyParser.json());

const openai = new OpenAI({
  apiKey: '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', // Replace with your OpenAI API key
});

app.post('/api/init-assistant', async (req, res) => {
  try {
    
    const assistant = await openai.beta.assistants.create({
      name: 'Financial Assistant',
      instructions: `You are a financial assistant. You are expected to answer questions based on the provided financial data. The user will ask you to answer questions in these possible formats: Simple Response (String), Excel file, table. Responses should be given in one of three formats: string, table, or excel. You will only provide the response in the requested format. For each format, the response should be structured as follows:

For the string format, the JSON structure should be:
{
  "response_type": "string",
  "data": {
    "comments": "Any additional comments or remarks."
  },
}

For the excel format, the JSON structure should be:
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

You will answer only in the specified format (string, table, or excel) and include the "response_type" attribute in the response to indicate the format used. The headers in excel file and table are just given as an example for you to understand. So, they need to be adjusted according to the financial data headers provided to you later in this conversation. So, use them as headers for both excel and table. Do not provide all formats in one response; answer based on the type requested. Financial data will be provided in a through JSON. The answers should reflect this data.`,
      tools: [{ type: 'code_interpreter' }],
      model: 'gpt-4o-mini',
    });
    
    res.json({ assistantId: assistant.id });
  } catch (error) {
    console.error('Error initializing assistant :', error.message);
    res.status(500).send('Failed to create assistant ');
  }
});
app.post('/api/init-thread', async (req, res) => {
  try {
   
    const thread = await openai.beta.threads.create();
    res.json({ threadId: thread.id });
  } catch (error) {
    console.error('Error initializing thread:', error.message);
    res.status(500).send('Failed to create thread');
  }
});

app.post('/api/feed-data', async (req, res) => {
  try {
    const { financialData,threadId,assistantId } = req.body;

    if (!financialData || !Array.isArray(financialData)) {
      return res.status(400).send('Invalid financial data. It should be an array of objects.');
    }
    console.log(threadId)
    const financialDataMessage = `
      Here is the chunk financial data for the last 60 days you will receive more chunks but consider this all as single soruce data:
      ${JSON.stringify(financialData)}
    `;
    const messageResponse = await openai.beta.threads.messages.create(threadId, {
      role: 'user',
      content: financialDataMessage,
    });
    const runResponse = await openai.beta.threads.runs.createAndPoll(threadId, {
      assistant_id: assistantId,
      temperature:0.1
    });
    res.json({ threadId: threadId});
  } catch (error) {
    console.error('Error initializing thread:', error.message);
    res.status(500).send('Failed to create thread');
  }
});

app.post('/api/get-response', async (req, res) => {
  const { threadId, assistantId, question } = req.body;

  if (!threadId || !assistantId || !question) {
    return res.status(400).send('threadId, assistantId, and question are required');
  }

  try {
    const messageResponse = await openai.beta.threads.messages.create(threadId, {
      role: 'user',
      content: question,
    });
    const runResponse = await openai.beta.threads.runs.createAndPoll(threadId, {
      assistant_id: assistantId,
      temperature:0.1
    });
    console.log(runResponse)
    if (runResponse.status === 'completed') {
      const messages = await openai.beta.threads.messages.list(
        runResponse.thread_id
      );
      for (const message of messages.data) {
        console.log(`${message.role} > ${message.content[0].text.value}`);
        break;
      }
    } else {
      console.log(runResponse.status);
    }
    res.json({ response: runResponse.data });
  } catch (error) {
    console.error('Error running thread or getting response:', error.message);
    res.status(500).send('Failed to get response');
  }
});

const port = 3000;
app.listen(port, () => {
  console.log(`Server running on http://localhost:${port}`);
});
