# Blind Date App - Client

Frontend UI for the Blind Date application, built with Next.js 15.

## Overview

This is the **frontend-only** client application. All backend logic, database access, and API endpoints are in the separate `server/` directory.

## Tech Stack

-   **Framework**: Next.js 15 (App Router)
-   **Language**: TypeScript
-   **Styling**: CSS Modules (no Tailwind by default)

## Getting Started

### Prerequisites
-   Node.js (v18+)
-   The backend server running (see `../server/README.md`)

### Installation

```bash
npm install
```

### Running the Client

Development mode:
```bash
npm run dev
```

The app will run on `http://localhost:3000`

Production build:
```bash
npm run build
npm start
```

## Project Structure

```
src/
└── app/          # Next.js App Router pages
```

## Connecting to Backend

The client communicates with the backend API at `http://localhost:3001` (configurable via environment variables).

Create a `.env.local` file:
```
NEXT_PUBLIC_API_URL=http://localhost:3001
```

## Development Notes

-   This is a **UI-only** project
-   No database access or business logic here
-   All data fetching happens via REST API calls to the server
