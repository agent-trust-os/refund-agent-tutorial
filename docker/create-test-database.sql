-- A second, empty database for the tests, so they never touch the app's data in "refund".
CREATE DATABASE refund_test;
-- The LangGraph app keeps its own data, so it never shares tables with the FastAPI app.
CREATE DATABASE refund_langgraph;
