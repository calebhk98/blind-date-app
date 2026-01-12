/**
 * @jest-environment node
 */

/**
 * Purpose: Tests for Profile Service using Repository Pattern.
 * Overview: Covers creation, validation, and error handling for user profiles.
 */
import { ProfileService } from './profile.service'
import { PrismaProfileRepository } from '@/repositories/prisma-profile.repository'
import { PrismaUserRepository } from '@/repositories/prisma-user.repository'

// Integration Test using Real Prisma Repo
describe('ProfileService', () => {
    let testUserId: string;
    let service: ProfileService;
    let userRepo: PrismaUserRepository;
    let profileRepo: PrismaProfileRepository;

    beforeAll(async () => {
        userRepo = new PrismaUserRepository();
        profileRepo = new PrismaProfileRepository();
        service = new ProfileService(profileRepo);

        // Create a unique test user
        const user = await userRepo.create(`test-repo-${Date.now()}@example.com`)
        testUserId = user.id
    })

    afterEach(async () => {
        await profileRepo.deleteByUserId(testUserId)
    })

    // Happy Path 1
    it('creates a profile for an existing user', async () => {
        const profile = await service.createProfile(testUserId, {
            bio: 'Hello world',
            preferences: { age: 25 },
            dealBreakers: { smoker: false }
        })
        expect(profile.id).toBeDefined()
        expect(profile.userId).toBe(testUserId)
        expect(profile.bio).toBe('Hello world')
        expect(JSON.parse(profile.preferences)).toEqual({ age: 25 })
    })

    // Happy Path 2
    it('creates a profile without bio', async () => {
        const profile = await service.createProfile(testUserId, {
            preferences: { open: true },
            dealBreakers: {}
        })
        expect(profile.bio).toBeNull()
        expect(JSON.parse(profile.dealBreakers)).toEqual({})
    })

    // Fail Path 1
    it('throws error if user does not exist', async () => {
        // Note: Prisma will throw Foreign Key constraint violation
        await expect(service.createProfile('invalid-uuid', {
            bio: 'Fail',
            preferences: {},
            dealBreakers: {}
        })).rejects.toThrow()
    })

    // Fail Path 2
    it('throws error if profile already exists', async () => {
        await service.createProfile(testUserId, { preferences: {}, dealBreakers: {} })
        await expect(service.createProfile(testUserId, {
            preferences: {},
            dealBreakers: {}
        })).rejects.toThrow(/Profile already exists/) // Specific error from Service
    })

    // Fail Path 3
    it('throws error if bio is too long', async () => {
        const longBio = 'a'.repeat(501)
        await expect(service.createProfile(testUserId, {
            bio: longBio,
            preferences: {},
            dealBreakers: {}
        })).rejects.toThrow(/Bio too long/)
    })
})
