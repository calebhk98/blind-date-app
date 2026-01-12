/**
 * Purpose: Prisma implementation of IMatchRepository.
 */
import prisma from '@/lib/prisma'
import { IMatchRepository, CreateMatchInput } from './interfaces'
import { Match } from '@prisma/client'

export class PrismaMatchRepository implements IMatchRepository {
    async findExisting(userAId: string, userBId: string): Promise<Match | null> {
        return prisma.match.findFirst({
            where: {
                OR: [
                    { userAId: userAId, userBId: userBId },
                    { userAId: userBId, userBId: userAId }
                ]
            }
        });
    }

    async create(data: CreateMatchInput): Promise<Match> {
        return prisma.match.create({
            data: {
                userAId: data.userAId,
                userBId: data.userBId,
                score: data.score,
                status: data.status
            }
        });
    }

    async deleteAll(): Promise<void> {
        await prisma.match.deleteMany();
    }
}
