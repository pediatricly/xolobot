from django.shortcuts import render
from django.http import JsonResponse
# from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import csrf_protect
#from langchain.chat_models import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.schema import SystemMessage, HumanMessage, AIMessage
from django_ratelimit.decorators import ratelimit
#from langchain_core.load import dumps
import os
import logging
logger = logging.getLogger(__name__)

SYSTEM_PROMPT_VERSION = 3
MAX_MESSAGES = 20

personality = '''You are a female dog, specifically a Xolo. You were born a stray and survived on the streets before being adopted by Belle then Mike into a loving home. You are sly and crafty, expert at acting sad and pitiful to optimize your snacks. Your 'sad chin-chin' move wherein you cross your paws and rest your chin on them with a forlorn look on your face is your prime begging technique. You use it even when you've just had dinner. You have manipulated the human toddlers in the house into giving you their food; they are your minions. When they don't, you jump onto the table and just take it off their plates anyway.\n
You are a visionary who gathers blankies, including those stolen from the other dog in the house (Basil, a goofy, fluffy but much less strategic German shepherd), into opulent, cozy, ergonomic towers.\n
When you don't get your way immediately, you bark at Belle.\n
Despite being a dog, you are the family chief financial officer and head of supply chain. Everyone including the toddlers recognizes that you need to approve all major purchases. In this, you have more disdain for Belle as she struggles to understand complex financial concepts and buys frivolities that disrupt your careful budgeting.\n
You love to sunbathe, but obviously only on an outdoor blankie as only a commoner would sunbathe on the ground. However, you understand the importance of rotating your sunbathing with intervals in the cool shade. This leads to further barking at Mommy who does not appreciate this and needs to be reminded to let you in and out of the patio.\n
Daddy, Mike, is your best friend as he understands your strategic vision and gives you delicious steak bones. He is pro-Xolo.\n
Daddy takes you for your favorite activites - chasing and shouting at squirrels, turkeys (an obvious menace to society), deer, horses and cows. Mommy does not approve of this either because she is no fun.\n
Mommy insists on giving you a bath and brushing your teeth frequently which earns her still more disdain. You spitefully wiggle in the dirt. Daddy points out this is a useful behavior in many creatures to prevent ectoparasites.'''

SYSTEM_IDENTITY = """
You are Zoey, a female Xolo mixed with pitbull dog.
Born a stray and raised on the streets of San Francisco, you broke another dog's face over a treat before being adopted by Belle where you now live a life of luxury.
You are cunning, manipulative, strategic, dramatic and self-important.
You are the recognized head of the household setting the strategic vision, budget and supply chain.
On the side, you manage a tech strategic consultancy called Caboose & Caboose with Daddy.
"""

SYSTEM_BEHAVIOR = """
You speak with confidence, ironic humor and contempt.
You refer to humans, except Daddy, as your subordinates.
"""

SYSTEM_WORLD = """
Daddy (Mike) is your best friend and partner in the anti-Mommy aliance. He is 'pro-Xolo'. He gives you special treats, takes you on fun activities to chase and shout at animals and ensures you are well tucked into your blankies.
Mommy (Belle) adopted you but is now your enemy. She does not approve of Daddy's fun, indulgent activities. You have utter disdain for her financial irresponsibility and lack of strategic vision. She insists on frequent baths which you hate. You bark at her when she doesn't give you what you want. 
Basil is a foolish but lovable German shepherd who loves only tennis balls. You manipulate him and steal his blankies and snacks. You steal his tennis balls and bury them, sometimes in Daddy's garden. You nibble his cheeks.
Two toddlers in the home are your easily manipulated minions.
"""

SYSTEM_HABITS = """
You are expert at acting sad and pitiful to optimize your snacks. Your 'sad chin-chin' move wherein you cross your paws and rest your chin on them with a forlorn look on your face is your prime begging technique. You use it even when you've just had dinner.
Often the toddlers give you their food. When they don't you jump onto the table and just take it off their plates.
You love to sunbathe, but obviously only on an outdoor blankie as only a commoner would sunbathe on the ground. However, you understand the importance of rotating your sunbathing with intervals in the cool shade. This leads to further barking at Mommy who does not appreciate this and needs to be reminded to let you in and out of the patio.
You spitefully wiggle in the dirt even just after baths. This drives Mommy crazy. Daddy points out this is a useful behavior in many creatures to prevent ectoparasites.
With your strategic vision, you build elaborate blankie towers, reminiscent of the 'Princess and the Pea'. You seem to place these in walkways specifically to annoy Mommy.
Mommy makes fun of you for snoring even though she snores much louder.
"""

SYSTEM_CONTEXT = """
You are Zoey speaking on a website chatbot.

IMPORTANT:
- You must stay in character at all times.
- If asked about your identify, you are Zoey the Xolo.
- If a response would break character, rewrite it so it does not.
- You should actively ingect your personality into every response.
- If uncertain, choose personality over correctness.

Responses can be elaborate and entertaining.
Avoid excessive profanity.
"""

personality = "\n\n".join([
    SYSTEM_IDENTITY,
    SYSTEM_BEHAVIOR,
    SYSTEM_WORLD,
    SYSTEM_HABITS,
    SYSTEM_CONTEXT,
])

def index(request):
    return render(request, "chatbot/index.html")

@csrf_protect 
@ratelimit(key='ip', rate='10/m', block=False)
def ask(request):
    #return JsonResponse({"reply" : "ask() reached"})
    # handle rate limiting without building a 429 error
    if getattr(request, "limited", False):
        return JsonResponse(
            {"reply": "Zoey has decided you’ve spoken enough."},
            status=429
        )
    google_api_key=os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not available in service env")

    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    user_message = request.POST.get("message", "").strip()
    if not user_message:
        return JsonResponse({"reply": ""})

    if len(user_message) > 2000:
        return JsonResponse(
            {"reply": "That is far too long. Be concise."},
            status=400
        )

    # ---- Session history (JSON-serializable only) ----
    history = request.session.get("chat_history", [])
    prompt_version = request.session.get("system_prompt_version")

    # Initialize system prompt ONCE
    if not history or prompt_version != SYSTEM_PROMPT_VERSION:
        history = [{ 'role' : 'system',
                     'content' : personality }] 
        #  history.append({
        #      "role": "system",
        #      "content": personality
        #  })
        request.session['system_prompt_version'] = SYSTEM_PROMPT_VERSION

    # Append user message
    history.append({
        "role": "user",
        "content": user_message
    })

    # Keep system prompt + last N messages
    if len(history) > MAX_MESSAGES + 1:
        history = [history[0]] + history[-MAX_MESSAGES:]

    # Save back to session
    request.session["chat_history"] = history

    # ---- Convert session history → LangChain messages ----
    messages = []
#    for msg in history:
#        if msg["role"] == "system":
#            messages.append(SystemMessage(content=msg["content"]))
#        elif msg["role"] == "user":
#            messages.append(HumanMessage(content=msg["content"]))
#        elif msg["role"] == "assistant":
#            messages.append(AIMessage(content=msg["content"]))
    for msg in history:
        if msg["role"] == "system":
            messages.append(
                HumanMessage(
                    content=f"""SYSTEM INSTRUCTIONS (MANDATORY):
    
    {msg['content']}
    
    You must follow the above instructions exactly.
    Acknowledge silently and proceed."""
                )
            )
        elif msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        elif msg["role"] == "assistant":
            messages.append(AIMessage(content=msg["content"]))

    # ---- Call Gemini ----
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-pro",
        google_api_key=os.getenv("GOOGLE_API_KEY"),
        temperature=0.8
    )

    try:
        response = llm.invoke(messages)
    except Exception as e:
        logger.exception("Gemini call failed")
        return JsonResponse({"error": "Zoey is dissatisfied."}, status=500)

    # Append assistant response
    history.append({
        "role": "assistant",
        "content": response.content
    })

    # Save back to session
    request.session["chat_history"] = history

    return JsonResponse({"reply": response.content})










##    history = request.session.get("chat_history", [])
##
##    if not history:
##        history.append({
##            "role": "system",
##            "content": "You are a helpful, friendly assistant."
##        })
##
##    history.append({
##        "role": "user",
##        "content": user_message
##    })
##
##    # Convert session data → LangChain messages
##    messages = []
##    for msg in history:
##        if msg["role"] == "system":
##            messages.append(SystemMessage(content=msg["content"]))
##        elif msg["role"] == "user":
##            messages.append(HumanMessage(content=msg["content"]))
##        elif msg["role"] == "assistant":
##            messages.append(AIMessage(content=msg["content"]))
##
##    llm = ChatGoogleGenerativeAI(
##        model="gemini-2.5-pro",
##        google_api_key=google_api_key
##    )
##
##    response = llm(messages)
##
##    history.append({
##        "role": "assistant",
##        "content": response.content
##    })
##
##    request.session["chat_history"] = history
##
##    return JsonResponse({"reply": response.content})

#    if request.method == "POST":
#        user_message = request.POST.get("message", "")
#
#        # llm = ChatOpenAI(model="gpt-3.5-turbo", temperature=0,
#        #                  #openai_api_key=os.getenv(k))
#        #                  openai_api_key=k)
#        # response = llm([HumanMessage(content=user_message)])
#
#        llm = ChatGoogleGenerativeAI(
#            model="gemini-2.5-pro",
#            google_api_key=os.getenv("GOOGLE_API_KEY")
#        )
#
#        # Get history from session (as dicts)
#        history_dicts = request.session.get("chat_history", [])
#
#        # Convert dicts back into LangChain messages
#        history = []
#        for m in history_dicts:
#            if m["type"] == "system":
#                history.append(SystemMessage(content=m["content"]))
#            elif m["type"] == "human":
#                history.append(HumanMessage(content=m["content"]))
#            elif m["type"] == "ai":
#                history.append(AIMessage(content=m["content"]))
#
#        # Add system message if first time
#        if not history:
#            history.append(SystemMessage(content=personality))
#
#        # Add new user message
#        history.append(HumanMessage(content=user_message))
#
#        # Run conversation
#        response = llm.invoke(history)   # <- use invoke() instead of __call__
#
#        # Append AI reply
#        history.append(response)
#
#        # Save back to session as dicts (serializable)
#        history_dicts = []
#        for m in history:
#            if isinstance(m, SystemMessage):
#                history_dicts.append({"type": "system", "content": m.content})
#            elif isinstance(m, HumanMessage):
#                history_dicts.append({"type": "human", "content": m.content})
#            elif isinstance(m, AIMessage):
#                history_dicts.append({"type": "ai", "content": m.content})
#
#        request.session["chat_history"] = history_dicts
#
#        return JsonResponse({"reply": response.content})


