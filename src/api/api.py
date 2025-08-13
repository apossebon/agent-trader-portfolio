from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Depends
import logging
from src.agents.trader_agent import get_trader_agent
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage

# Query request model
# Represents a request for querying 

from dotenv import load_dotenv
load_dotenv(override=True)  # Load environment variables from .env file

class QueryRequest(BaseModel):
    question: str
    user_id: Optional[str] = "alysson.possebon@gmail.com"
    thread_id: Optional[str] = "session-ID_123"

class QueryResponse(BaseModel):
    answer: str
    messages: List[str]  # optional follow-up messages

# FastAPI application
app = FastAPI(title="Agent Trader - Portfolio - API", version="1.0.0", description="API for querying the Agent Trader portfolio system.")

# Logger
logger = logging.getLogger("uvicorn.error")

# Startup/shutdown hooks
@app.on_event("startup")
async def on_startup():
    logger.info("Agent Trader API starting up")
    app.state.trader_agent = await get_trader_agent()

@app.on_event("shutdown")
async def on_shutdown():
    logger.info("Agent Trader API shutting down")
    # e.g., cleanup resources
    # await app.state.http.aclose()


# dependecies 
def get_agent() -> create_react_agent:
    agent = getattr(app.state, "trader_agent", None)
    if agent is None:
        raise RuntimeError("Agent not ready.")
    return agent



# endpoint health check
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# endpoint for querying with streaming response
@app.post("/query/streaming", response_model=QueryResponse)
async def query(request: QueryRequest, agent=Depends(get_agent)):
    # Simulate a query response
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Pergunta vazia.")

    session_cfg = {
        "configurable": {
            "user_id": request.user_id,
            "thread_id": request.thread_id,
        },
        "recursion_limit": 1000,
    }

    langchain_input = {"messages": [HumanMessage(content=request.question)]}

    async def token_streamer():
        try:
            async for step, metadata in agent.astream(langchain_input,config=session_cfg, stream_mode="messages"):
                try:
                    if metadata["langgraph_node"] == "agent" and (text := step.text()):
                        # print(text, end="")
                        yield text
                    elif metadata["langgraph_node"] == "tools" and (text := step.text()):
                        print(text, end="")
                        # yield text
                    # else:
                    #     print(f"metadata: {metadata}")
                    #     print("\n\ntexto")
                    #     print(text, end="")
                except Exception as e:
                    print(f"Error processing step: {e}")
                    continue
        except Exception as e:
            print(f"Stream error: {e}")
            yield f"data: Error occurred: {str(e)}\n\n"
        # finally:
        #     yield f"data: [DONE]\n\n"  # Signal end of stream
                
    return StreamingResponse(
        token_streamer(), 
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )