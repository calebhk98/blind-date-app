/**
 * Purpose: Prisma implementation of IProfileRepository.
 */
import prisma from '@/lib/prisma'
import { IProfileRepository, CreateProfileInput } from './interfaces'
import { Profile } from '@prisma/client'

export class PrismaProfileRepository implements IProfileRepository {
    async findByUserId(userId: string): Promise<Profile | null> {
        return prisma.profile.findUnique({ where: { userId } })
    }

    async create(userId: string, data: CreateProfileInput): Promise<Profile> {
        return prisma.profile.create({
            data: {
                userId,
                bio: data.bio,
                preferences: data.preferences,
                dealBreakers: data.dealBreakers
            }
        })
    }

    async deleteByUserId(userId: string): Promise<void> {
        await prisma.profile.deleteMany({ where: { userId } })
    }
}
