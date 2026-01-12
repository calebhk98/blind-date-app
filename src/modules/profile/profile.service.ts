/**
 * Purpose: Service for managing user profiles.
 * Overview: Handles creation, updates, and validation of profiles using Repository Pattern.
 */
import { IProfileRepository, CreateProfileInput } from '@/repositories/interfaces'

export class ProfileService {
    constructor(private profileRepo: IProfileRepository) { }

    async createProfile(userId: string, data: CreateProfileInput) {
        // Validate bio length
        if (data.bio && data.bio.length > 500) {
            throw new Error('Bio too long. Max 500 characters.')
        }

        // Check if profile already exists
        const existing = await this.profileRepo.findByUserId(userId)

        if (existing) {
            throw new Error('Profile already exists for this user')
        }

        // Create profile
        const profile = await this.profileRepo.create(userId, {
            bio: data.bio,
            preferences: JSON.stringify(data.preferences),
            dealBreakers: JSON.stringify(data.dealBreakers)
        })

        return profile
    }
}
