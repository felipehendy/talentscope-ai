from app import app

# Vercel handler
def handler(request):
    return app(request.environ, request.start_response)

if __name__ == "__main__":
    app.run()