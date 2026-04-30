import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import {supabase} from '@/lib/supabase';
import { useAuthStore } from "@/store/auth-store";
import { UserProfileView } from '@/types/api';

export function useProfile() {
    const user = useAuthStore((state) => state.user);
    return useQuery({
        queryKey: ['profile'],
        queryFn: async () => {
            if (!user) {
                throw new Error('User not authenticated');
            }

            const { data } = await supabase
                .from('v_user_profile')
                .select('*')
                .eq('user_id', user.id)
                .throwOnError();
            return data as UserProfileView[];
        },
    });
}

export function useUpdateProfile() {
    const user = useAuthStore((state) => state.user);

    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async (profile: Partial<UserProfileView>) => {
            if (!user) {
                throw new Error('User not authenticated');
            }
            const { error } = await supabase
                .from("users")
                .update({
                    phone: profile.phone,
                    whatsapp_opt_in: profile.whatsapp_opt_in,
                    dob: profile.dob,
                    qualifications: profile.qualifications,
                    id_type: profile.id_type,
                    id_number: profile.id_number,
                    country: profile.owner_country,
                    province: profile.owner_province,
                    postal_code: profile.owner_postal_code,
                    full_name: profile.full_name,
                    race: profile.race,
                    gender: profile.gender,
                })
                .eq("id", profile.user_id);
            if(!profile.business_id) {
                const { error: businessError } = await supabase
                    .from("businesses")
                    .insert({
                        profile_id: profile.user_id,
                    });
                if (businessError) {
                    console.error("Error saving business details:", businessError);
                    throw businessError;
                }
            }

            if (error) {
                console.error("Error saving personal details:", error);
                throw error;
            }
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['profile'] });
        },
    });
}