curl http://model-runner.docker.internal/engines/llama.cpp/v1/chat/completions \ 
    -H "Content-Type: application/json" \
    -d '{
        "model": "ai/gpt-oss:latest",
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": "Please write 500 words about the fall of Rome."
            }
        ]
    }'

