const DEFAULT_API_BASE = "https://presidio-test-api.bravesand-5605c72b.southeastasia.azurecontainerapps.io";

const ENDPOINTS = {
  "text-extracted": "/api/extracted-entities",
  "text-anonymized": "/api/anonymized-text",
  "pdf-extracted": "/api/pdf/extracted-entities",
  "pdf-anonymized": "/api/pdf/anonymized-text",
};

module.exports = async function handler(request, response) {
  if (request.method !== "POST") {
    return sendJson(response, 405, {
      error: "Method not allowed. Use POST.",
      operations: Object.keys(ENDPOINTS),
    });
  }

  const requestUrl = new URL(request.url, `https://${request.headers.host || "localhost"}`);
  const operation = requestUrl.searchParams.get("operation");
  const endpoint = ENDPOINTS[operation];

  if (!endpoint) {
    return sendJson(response, 400, {
      error: "Missing or invalid operation.",
      operations: Object.keys(ENDPOINTS),
    });
  }

  const apiBase = (process.env.AZURE_API_BASE || DEFAULT_API_BASE).replace(/\/+$/, "");
  const body = await readBody(request);
  const contentType = request.headers["content-type"] || "application/octet-stream";

  try {
    const apiResponse = await fetch(`${apiBase}${endpoint}`, {
      method: "POST",
      headers: {
        "content-type": contentType,
      },
      body,
    });

    const responseBody = await apiResponse.text();
    response.statusCode = apiResponse.status;
    response.setHeader("content-type", apiResponse.headers.get("content-type") || "application/json");
    response.end(responseBody);
  } catch (error) {
    sendJson(response, 502, {
      error: "Could not connect to the Azure API.",
      details: String(error && error.message ? error.message : error),
    });
  }
};

function sendJson(response, statusCode, payload) {
  response.statusCode = statusCode;
  response.setHeader("content-type", "application/json");
  response.end(JSON.stringify(payload));
}

function readBody(request) {
  if (Buffer.isBuffer(request.body)) {
    return Promise.resolve(request.body);
  }

  if (typeof request.body === "string") {
    return Promise.resolve(Buffer.from(request.body));
  }

  if (request.body && typeof request.body === "object") {
    return Promise.resolve(Buffer.from(JSON.stringify(request.body)));
  }

  return new Promise((resolve, reject) => {
    const chunks = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}
