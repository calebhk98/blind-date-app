/**
 * @jest-environment node
 */

/**
 * Purpose: Integration tests for Matching Service.
 * Overview: Verifies database interactions and full matching flow using Repositories.
 */
import { MatchingService } from './matching.service'
import { PrismaUserRepository } from '@/repositories/prisma-user.repository'
import { PrismaMatchRepository } from '@/repositories/prisma-match.repository'
import { PrismaProfileRepository } from '@/repositories/prisma-profile.repository'
import prisma from '@/lib/prisma'

describe('MatchingService', () => {
    let service: MatchingService;
    let userRepo: PrismaUserRepository;
    let matchRepo: PrismaMatchRepository;
    let profileRepo: PrismaProfileRepository;

    // Cleanup helper
    const cleanup = async () => {
        await matchRepo.deleteAll();
        // ProfileRepo delete logic needs expansion or direct DB access for cleanup
        await prisma.profile.deleteMany();
        await prisma.user.deleteMany();
    }

    beforeAll(() => {
        userRepo = new PrismaUserRepository();
        matchRepo = new PrismaMatchRepository();
        profileRepo = new PrismaProfileRepository();
        service = new MatchingService(userRepo, matchRepo);
    })

    beforeEach(async () => {
        await cleanup();
    })

    afterAll(async () => {
        await cleanup();
    })

    const createUserWithProfile = async (email: string, credits: number, prefs: any, breakers: any) => {
        const user = await userRepo.create(email, credits);
        await profileRepo.create(user.id, {
            bio: 'Test bio',
            preferences: JSON.stringify(prefs),
            dealBreakers: JSON.stringify(breakers)
        });
        return user;
    }

    // Happy 1
    it('creates a match for compatible users with credits', async () => {
        const u1 = await createUserWithProfile('u1@test.com', 10, { a: 1 }, {})
        const u2 = await createUserWithProfile('u2@test.com', 10, { a: 1 }, {})

        const count = await service.findAndCreateMatches();
        expect(count).toBeGreaterThan(0);

        const match = await matchRepo.findExisting(u1.id, u2.id);
        expect(match).toBeDefined();
    })

    // Happy 2
    it('does not match users with 0 credits', async () => {
        const u1 = await createUserWithProfile('u1@test.com', 0, { a: 1 }, {})
        const u2 = await createUserWithProfile('u2@test.com', 10, { a: 1 }, {})

        const count = await service.findAndCreateMatches();
        expect(count).toBe(0);
    })

    // Happy 3
    it('does not match if deal breaker exists', async () => {
        const u1 = await createUserWithProfile('u1@test.com', 10, { smoker: true }, {})
        const u2 = await createUserWithProfile('u2@test.com', 10, { smoker: false }, { smoker: false })

        const count = await service.findAndCreateMatches();
        expect(count).toBe(0);
    })

    // Happy 4
    it('does not duplicate existing matches', async () => {
        const u1 = await createUserWithProfile('u1@test.com', 10, { a: 1 }, {})
        const u2 = await createUserWithProfile('u2@test.com', 10, { a: 1 }, {})

        // First run
        await service.findAndCreateMatches();

        // Second run
        const count = await service.findAndCreateMatches();
        expect(count).toBe(0);
    })

    // Edge 1
    it('handles empty database gracefully', async () => {
        const count = await service.findAndCreateMatches();
        expect(count).toBe(0);
    })
})
