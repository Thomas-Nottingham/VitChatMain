// const readEnvString = (value: unknown): string | undefined =>
//   typeof value === "string" && value.trim().length > 0
//     ? value.trim()
//     : undefined;

// export const CHATKIT_API_URL =
//   readEnvString(import.meta.env.VITE_CHATKIT_API_URL) ?? "/chatkit";

// /**
//  * ChatKit requires a domain key at runtime. Use the local fallback while
//  * developing, and register a production domain key for deployment:
//  * https://platform.openai.com/settings/organization/security/domain-allowlist
//  */
// export const CHATKIT_API_DOMAIN_KEY =
//   readEnvString(import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY) ??
//   "domain_pk_localhost_dev";


  
// config.tsx

// Hardcoded production values for testing
// export const CHATKIT_API_URL = "https://thegiftvaults.com/api/chatkit";

// /**
//  * ChatKit requires a domain key at runtime. Use the local fallback while
//  * developing, and register a production domain key for deployment:
//  * https://platform.openai.com/settings/organization/security/domain-allowlist
//  */
// export const CHATKIT_API_DOMAIN_KEY =
//   "domain_pk_695a6b23af148190abd36e809cd2434e0aeee9e3c4be59d7";

const readEnvString = (value: unknown): string | undefined =>
  typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;

export const CHATKIT_API_URL =
  readEnvString(import.meta.env.VITE_CHATKIT_API_URL) ?? "http://localhost:8000/chatkit";

export const CHATKIT_API_DOMAIN_KEY =
  readEnvString(import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY) ?? "domain_pk_localhost_dev";
