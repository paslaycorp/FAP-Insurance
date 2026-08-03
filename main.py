import uvicorn
from fap_insurance.api import app

if __name__ == "__main__":
    uvicorn.run(
        "fap_insurance.api:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
    )
