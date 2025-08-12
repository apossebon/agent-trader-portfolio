import streamlit as st
import time
import requests
import os
import uuid

DEFAULT_API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Agentic Trading", page_icon="💰")  # ← title and favicon
st.title("💰 Trader Agent - Portfolio")  # ← title

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

session_id = st.session_state.session_id  # ✅ correto: persistente

thinking = False


def chat_stream(prompt):
    # response = f'You said, "{prompt}" ...interesting.'
   
    for char in prompt:
        char = char.replace("$", "\\$")
        yield char
        time.sleep(0.001)


def save_feedback(index):
    st.session_state.history[index]["feedback"] = st.session_state[f"feedback_{index}"]



if "history" not in st.session_state:
    st.session_state.history = []

for i, message in enumerate(st.session_state.history):
    with st.chat_message(message["role"], avatar=message["avatar"]):
        st.write(message["content"])
        if message["role"] == "assistant":
            feedback = message.get("feedback", None)
            st.session_state[f"feedback_{i}"] = feedback
            st.feedback(
                "thumbs",
                key=f"feedback_{i}",
                disabled=feedback is not None,
                on_change=save_feedback,
                args=(i,),
            )

if prompt := st.chat_input("Say something"):
    with st.chat_message("user", avatar="🦖"):
        st.write(prompt)

        # 2️⃣ Chamada à API com streaming
        payload = {
            "question": prompt,
            "user_id": "apossebon",
            "thread_id": session_id,
        }
        api_url = DEFAULT_API_URL.rstrip("/") + "/query/streaming"

        streamed_text = ""  # ✅ inicialize fora do try
        response = None

        with st.spinner("…"):
            
            try:
                response = requests.post(api_url, json=payload, stream=True, timeout=60*5)
                resp = response.raise_for_status()
                # streamed_text = response.text  # ✅ defina mesmo em caso de erro
                
                st.empty()

            
                        
            except Exception as exc:
                error_msg = f"⚠️ Erro ao chamar API: {exc}"
                streamed_text = error_msg  # ✅ defina mesmo em caso de erro
                


    st.session_state.history.append({"role": "user", "avatar":"🦖", "content": prompt})
    with st.chat_message("assistant", avatar="🤖"):
        if response:
            streamed_text = ""
            thinking = False
            buffer = ""
            aux = ""
            
            with st.spinner("Thinking ",show_time=True):
              

                    # streamed_text = response.iter_content(decode_unicode=True)
                    # st.write_stream(chat_stream(streamed_text))
                # Detect if the chunk contains a markdown table and render it properly
                
                    
                streamed_text = st.write_stream(chat_stream(response.iter_content(decode_unicode=True)))


                
            
        else:
            streamed_text = "Error: No response received"

        st.feedback(
            "thumbs",
            key=f"feedback_{len(st.session_state.history)}",
            on_change=save_feedback,
            args=(len(st.session_state.history),),
        )
        
    st.session_state.history.append({"role": "assistant",  "avatar":"🤖", "content": streamed_text})