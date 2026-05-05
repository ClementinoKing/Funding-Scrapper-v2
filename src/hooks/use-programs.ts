import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import {supabase} from '@/lib/supabase';
import { useAuthStore } from "@/store/auth-store";
import { UserProfileView } from '@/types/api';

export function usePrograms() {
    const user = useAuthStore((state) => state.user);
    return useQuery({
        queryKey: ['programs'],
        queryFn: async () => {
            if (!user) {
                throw new Error('User not authenticated');
            }

            const { data } = await supabase
                .from('funding_programmes')
                .select('*')
                .throwOnError();
            return data;
        },
    });
}

export function useProgram(program_id: string) {
    const user = useAuthStore((state) => state.user);
    return useQuery({
        queryKey: ['program', program_id],
        queryFn: async () => {
            if (!user) {
                throw new Error('User not authenticated');
            }

            const { data } = await supabase
                .from('funding_programmes')
                .select('*')
                .eq('program_id', program_id)
                .throwOnError();
            return data?.[0];
        },
    });
}
