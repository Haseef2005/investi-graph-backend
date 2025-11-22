import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api_logger")

class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Log Request
        logger.info(f"Incoming Request: {request.method} {request.url}")
        
        try:
            response = await call_next(request)
            
            # Log Response
            process_time = time.time() - start_time
            logger.info(
                f"Request Completed: {request.method} {request.url} "
                f"Status: {response.status_code} "
                f"Duration: {process_time:.4f}s"
            )
            return response
        except Exception as e:
            process_time = time.time() - start_time
            logger.error(
                f"Request Failed: {request.method} {request.url} "
                f"Error: {str(e)} "
                f"Duration: {process_time:.4f}s"
            )
            raise
