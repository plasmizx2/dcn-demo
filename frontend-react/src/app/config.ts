// API Configuration
// Update this to point to your backend URL
export const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// Helper function to build API URLs
export function getApiUrl(path: string): string {
  // Remove leading slash if present to avoid double slashes
  const cleanPath = path.startsWith('/') ? path.slice(1) : path;
  
  // If API_BASE_URL is empty, use relative URLs (same domain)
  if (!API_BASE_URL) {
    return `/${cleanPath}`;
  }
  
  // Otherwise use the full URL
  return `${API_BASE_URL}/${cleanPath}`;
}

// Helper function for API fetch with better error handling
export async function apiFetch(path: string, options?: RequestInit): Promise<Response> {
  const url = getApiUrl(path);
  const response = await fetch(url, {
    ...options,
    credentials: 'include',
  });
  
  // Check if response is HTML instead of JSON
  const contentType = response.headers.get('content-type');
  if (!response.ok && contentType?.includes('text/html')) {
    throw new Error(`API returned HTML instead of JSON. Endpoint may not exist: ${url}`);
  }
  
  return response;
}
