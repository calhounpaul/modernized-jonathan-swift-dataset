THIS_DIR_PATH=$(dirname $(realpath $0))
OLLAMA_CACHE_FOLDER_PATH=$THIS_DIR_PATH/.ollama_cache
OLLAMA_WEB_FOLDER_PATH=$THIS_DIR_PATH/.ollama_web

if [ ! -d $OLLAMA_CACHE_FOLDER_PATH ]; then
    mkdir -p $OLLAMA_CACHE_FOLDER_PATH
fi
if [ ! -d $OLLAMA_WEB_FOLDER_PATH ]; then
    mkdir -p $OLLAMA_WEB_FOLDER_PATH
fi

docker kill open-webui
docker rm open-webui
docker rm /open-webui
sleep 3

docker run -d -p 3000:8080 -p 11434:11434 --gpus '"device=0,1"' -v $OLLAMA_CACHE_FOLDER_PATH:/root/.ollama \
    -v $OLLAMA_WEB_FOLDER_PATH:/app/backend/data --name open-webui --restart always \
    -e OLLAMA_HOST=0.0.0.0 \
    ghcr.io/open-webui/open-webui:ollama
