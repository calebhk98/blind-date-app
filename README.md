# Blind Date App

A unique dating application focusing on algorithmic matching and "blind dates" ($1/date model) with no initial messaging phase.

## Overview

This application uses a credit-based system where users fill out detailed profiles including "deal breakers". The system then runs a matching algorithm to find optimal pairs and arranges a date (location & time) without the users needing to chat first.

### Key Features
-   **Credit System**: Pay-per-date model.
-   **Algorithmic Matching**: Greedy scoring algorithm (O(N^2) for MVP) considering shared preferences and deal breakers.
-   **Deal Breakers**: Hard filters that prevent matches regardless of score.
-   **Clean Architecture**: Separation of concerns using Services and Repository Pattern.

## Tech Stack

-   **Framework**: Next.js 15 (App Router)
-   **Language**: TypeScript
-   **Database**: SQLite
-   **ORM**: Prisma (v5)
-   **Testing**: Jest + React Testing Library

## Architecture

The project follows a modular architecture with a strict **Repository Pattern** to abstract database access.

```
src/
├── lib/            # Shared utilities (Prisma singleton)
├── modules/        # Business Logic (Services)
│   ├── matching/   # Matching Engine
│   └── profile/    # Profile Management
├── repositories/   # Data Access Layer (Prisma Implementations)
│   ├── interfaces.ts           # Repository Interfaces
│   ├── prisma-user.repository.ts
│   ├── prisma-profile.repository.ts
│   └── prisma-match.repository.ts
└── app/            # Next.js App Router (UI & API)
```

### Database Abstraction
We define interfaces (e.g., `IUserRepository`) in `src/repositories/interfaces.ts`. Services depend on these interfaces, not the implementation. This allows swapping the DB layer (e.g., to MongoDB or specialized test mocks) without changing business logic.

## Getting Started

### Prerequisites
-   Node.js (v18+)
-   npm

### Installation

1.  Clone the repository and install dependencies:
    ```bash
    npm install
    ```

2.  Initialize the Database (SQLite):
    ```bash
    npx prisma db push
    ```

3.  Run the development server:
    ```bash
    npm run dev
    ```

## Testing

We practice **Test-Driven Development (TDD)**. Tests are isolated and run against a separate SQLite database (`test.db`) to avoid modifying development data.

### Running Tests
To run the full test suite (Sequential execution + DB Reset):
```bash
npm test
```

### Test Configuration
-   **`package.json`**: The test script sets `dotenv -e .env.test`, forcing the app to use the test database configuration.
-   **`jest.setup.ts`**: Configures the testing environment.
-   **`.env.test`**: Points `DATABASE_URL` to `file:./test.db`.

## License
[Proprietary/Internal Use]
