//
// Created by Raghavasimhan Sankaranarayanan on 03/30/22.
//

#ifndef UTIL_H
#define UTIL_H

#include "def.h"
#include <math.h>


namespace Util {
    float __fretLength(float fretNumber);
    int32_t __pos2Pulse(float pos, int direction = ENCODER_DIR);
    int32_t fret2Pos(float fretPos);
    template<typename T>
    bool interp(T q0, T qf, size_t N, float tb_cent = 0.2, T* curve = nullptr) {
        if (!curve)
            return false;

        if (q0 == qf) {
            for (int i = 0; i < N; ++i)
                curve[i] = q0;
            return true;
        }

        int nb = int(tb_cent * N);
        float a_2 = 0.5 * (qf - q0) / (nb * (N - nb));
        T tmp;

        for (int i = 0; i < nb; ++i) {
            tmp = a_2 * pow(i, 2);
            curve[i] = q0 + tmp;
            //  N-1, N-2, ... , N - nb
            curve[N - i - 1] = qf - tmp;
        }

        tmp = a_2 * pow(nb, 2);
        T qa = q0 + tmp;
        T qb = qf - tmp;
        linspace(qa, qb, N - (2 * nb), &curve[nb]);

        return true;
    }




    static void linspace(float start, float end, int N, float* array) {
        if (!array || N <= 0)
            return;

        for (int i = 0; i < N; ++i) {
            array[i] = start + ((i * 1.f / (N - 1)) * (end - start));
            //Serial.println(array[i] = start + ((i * 1.f / (N - 1)) * (end - start)));

        }
    }

    // Refer: https://cs.gmu.edu/~kosecka/cs685/cs685-trajectories.pdf
    static void interpWithBlend(float q0, float qf, int32_t N, float tb_cent, float* curve) {
        if (!curve)
            return;

        int nb = int(tb_cent * N);
        float a_2 = 0.5 * (qf - q0) / (nb * (N - nb));
        float tmp;

        for (int i = 0; i < nb; ++i) {
            tmp = a_2 * pow(i, 2);
            curve[i] = q0 + tmp;
            //  N-1, N-2, ... , N - nb
            curve[N - i - 1] = qf - tmp;

        }

        tmp = a_2 * pow(nb, 2);
        float qa = q0 + tmp;
        float qb = qf - tmp;
        linspace(qa, qb, N - (2 * nb), &curve[nb]);
    }

    // Compute instantaneous position and return true if the trajectory is complete
    static bool computeInstantaneousPosition(float t, float Xo, float Xf, float acc, float velocity, float& fInstantaneousPosition) {
        float eps = 5e-5;

        float deltaX = (Xf - Xo);
        float direction = deltaX >= 0 ? 1. : -1.;

        acc = direction * acc;
        velocity = direction * min(velocity, sqrt(abs(deltaX * acc)));

        float t1 = velocity / acc;
        float t2 = eps + deltaX / velocity;   // eps is added to make sure t2 > t1

        if (t <= t1) fInstantaneousPosition = Xo + (0. * t) + (0.5 * acc * pow(t, 2));                                // t <= t1
        else if ((t > t1) && (t <= t2)) fInstantaneousPosition = Xo + 0.5 * acc * pow(t1, 2) + (t - t1) * velocity;   // t1 < t <= t2
        else if (t > t2 && (t < t2 + t1)) fInstantaneousPosition = Xf + (0.5 * -(acc * pow(t1 + t2 - t, 2)));         // t2 < t < t1 + t2
        else {
            fInstantaneousPosition = Xf;
            return true;
        }

        return false;
    }

    static int interpWithBlend(float q0, float qf, float acc, float resolution, uint32_t N, float* curve = nullptr) {
        if (!curve)
            return 1;

        float tf = N * resolution;

        // a_2 = 0.5 * (qf - q0) / (Nb * (N - Nb))
        // (tb ** 2) - tb * tf + (qf - q0) / a = 0
        // D = tf * *2 - (4 * (qf - q0) / a)
        // tb = (tf - np.sqrt(D)) / 2

        float D = pow(tf, 2) - (4 * (qf - q0) / acc);
        if (D < 0) return 2;

        float tb = (tf - sqrt(D)) / 2;
        uint32_t Nb = ceil(tb / resolution);

        for (int i = 0; i < Nb; ++i) {
            float tmp = 0.5 * acc * pow(i * resolution, 2);
            curve[i] = q0 + tmp;
            curve[N - i - 1] = qf - tmp;
        }

        float tmp = 0.5 * acc * pow(tb, 2);

        linspace(q0 + tmp, qf - tmp, N - (2 * Nb), &curve[Nb]);

        return 0;
    }

    static void fill(float* arr, int length, float value) {
        for (int i = 0; i < length; ++i) {
            arr[i] = value;
        }
    }

    static void fill(int* arr, int length, int value) {
        for (int i = 0; i < length; ++i) {
            arr[i] = value;
        }
    }



} // namespace Util


#endif // UTIL_H
