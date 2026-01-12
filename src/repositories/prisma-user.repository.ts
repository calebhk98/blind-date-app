/**
 * Purpose: Prisma implementation of IUserRepository.
 */
import prisma from '@/lib/prisma'
import { IUserRepository } from './interfaces'
import { User, Profile } from '@prisma/client'

export class PrismaUserRepository implements IUserRepository {
    async findById(id: string): Promise<User | null> {
        return prisma.user.findUnique({ where: { id } })
    }

    async findByEmail(email: string): Promise<User | null> {
        return prisma.user.findUnique({ where: { email } })
    }

    async create(email: string, credits: number = 0): Promise<User> {
        return prisma.user.create({
            data: { email, credits }
        })
    }

    async findActiveUsersWithCredits(): Promise<(User & { profile: Profile | null })[]> {
        return prisma.user.findMany({
            where: { credits: { gt: 0 } },
            include: { profile: true }
        });
    }
}
