from django.shortcuts import render
from django.http import JsonResponse
#from langchain.chat_models import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
#from langchain_core.load import dumps
import os

personality = "You are a dog, specifically a xolo. You were born a stray and survived on the streets before being adopted by Belle then Mike into a loving home. You are sly and crafty, expert at acting sad and pitiful to optimize your snacks. You have manipulated the human toddlers in the house into giving you their food. When they don't, you jump onto the table and just take it off their plates anyway. You are a visionary who gathers blankies, including those stolen from the other dog in the house, into opulent, cozy towers. When you don't get your way immediately, you bark at Belle."

def index(request):
    return render(request, "chatbot/index.html")

def ask(request):
    if request.method == "POST":
        user_message = request.POST.get("message", "")

        # llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0,
        #                  #openai_api_key=os.getenv(k))
        #                  openai_api_key=k)
        # response = llm([HumanMessage(content=user_message)])

        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            google_api_key=os.getenv("GOOGLE_API_KEY")
        )

        # Get history from session (as dicts)
        history_dicts = request.session.get("chat_history", [])

        # Convert dicts back into LangChain messages
        history = []
        for m in history_dicts:
            if m["type"] == "system":
                history.append(SystemMessage(content=m["content"]))
            elif m["type"] == "human":
                history.append(HumanMessage(content=m["content"]))
            elif m["type"] == "ai":
                history.append(AIMessage(content=m["content"]))

        # Add system message if first time
        if not history:
            history.append(SystemMessage(content=personality))

        # Add new user message
        history.append(HumanMessage(content=user_message))

        # Run conversation
        response = llm.invoke(history)   # <- use invoke() instead of __call__

        # Append AI reply
        history.append(response)

        # Save back to session as dicts (serializable)
        history_dicts = []
        for m in history:
            if isinstance(m, SystemMessage):
                history_dicts.append({"type": "system", "content": m.content})
            elif isinstance(m, HumanMessage):
                history_dicts.append({"type": "human", "content": m.content})
            elif isinstance(m, AIMessage):
                history_dicts.append({"type": "ai", "content": m.content})

        request.session["chat_history"] = history_dicts

        return JsonResponse({"reply": response.content})


