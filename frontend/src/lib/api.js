import axios from "axios";

// This checks if a production API URL is set in Netlify, otherwise falls back to localhost for local testing
const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || "http://localhost:8000/api",
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("ud_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default api;
