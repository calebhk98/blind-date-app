/**
 * Purpose: Define interfaces for Data Access Layer to allow swapping implementations.
 */
import { User, Profile, Match } from '@prisma/client'

// Domain Types (re-using Prisma types for now, could be pure domain entities later)
export type CreateProfileInput = {
    bio?: string;
    preferences: string; // JSON
    dealBreakers: string; // JSON
}

export type CreateMatchInput = {
    userAId: string;
    userBId: string;
    score: number;
    status: string;
}

export interface IUserRepository {
    findById(id: string): Promise<User | null>;
    findByEmail(email: string): Promise<User | null>;
    create(email: string, credits?: number): Promise<User>;
    findActiveUsersWithCredits(): Promise<(User & { profile: Profile | null })[]>;
}

export interface IProfileRepository {
    findByUserId(userId: string): Promise<Profile | null>;
    create(userId: string, data: CreateProfileInput): Promise<Profile>;
    deleteByUserId(userId: string): Promise<void>; // For testing cleanup
}

export interface IMatchRepository {
    findExisting(userAId: string, userBId: string): Promise<Match | null>;
    create(data: CreateMatchInput): Promise<Match>;
    deleteAll(): Promise<void>; // For testing cleanup
}
