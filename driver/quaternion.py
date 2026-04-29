# quaternion.py — drop-in numpy quaternion, [w, x, y, z] convention
# Replacing pyquaternion to improve performance
import numpy as np

class Q:
    """Lightweight quaternion wrapping a numpy array [w, x, y, z].
    API-compatible with the parts of pyquaternion used in this codebase.
    """
    __slots__ = ('q',)

    def __init__(self, w=1.0, x=0.0, y=0.0, z=0.0, array=None, 
                axis=None, radians=None, degrees=None, matrix=None):
        if matrix is not None:
            self.q = Q.from_matrix(np.asarray(matrix, dtype=float)).q
        elif axis is not None:
            ax = np.asarray(axis, dtype=float)
            ax = ax / np.linalg.norm(ax)
            if degrees is not None:
                a = np.radians(degrees)
            elif radians is not None:
                a = float(radians)
            else:
                raise ValueError("axis requires either radians or degrees")
            s = np.sin(a / 2)
            self.q = np.array([np.cos(a / 2), ax[0]*s, ax[1]*s, ax[2]*s])
        elif array is not None:
            self.q = np.asarray(array, dtype=float)
        elif hasattr(w, '__len__') or isinstance(w, np.ndarray):
            # pyquaternion accepts Quaternion([w, x, y, z]) as first positional arg
            self.q = np.asarray(w, dtype=float)
        else:
            self.q = np.array([w, x, y, z], dtype=float)

    # ── properties ────────────────────────────────────────────────────────
    @property
    def w(self): return self.q[0]
    @property
    def x(self): return self.q[1]
    @property
    def y(self): return self.q[2]
    @property
    def z(self): return self.q[3]
    @property
    def norm(self): return float(np.linalg.norm(self.q))
    @property
    def normalised(self):
        n = np.linalg.norm(self.q)
        return Q(array=self.q / n)
    @property
    def conjugate(self):
        return Q(array=np.array([self.q[0], -self.q[1], -self.q[2], -self.q[3]]))
    @property
    def inverse(self): return self.conjugate   # unit quaternion assumption
    @property
    def is_unit(self): return abs(1.0 - np.dot(self.q, self.q)) < 1e-6
    @property
    def scalar(self): return self.q[0]
    @property  
    def vector(self): return self.q[1:] 
    @property
    def angle(self): return 2 * np.arccos(np.clip(self.q[0], -1.0, 1.0))
    @property
    def radians(self): return self.angle
    @property
    def degrees(self): return np.degrees(self.angle)
    @property
    def axis(self):
        """Unit vector of the rotation axis."""
        s = np.linalg.norm(self.q[1:])
        if s < 1e-10:
            return np.array([0.0, 0.0, 1.0])   
        return self.q[1:] / s



    # ── operators ─────────────────────────────────────────────────────────
    def __getitem__(self, idx): return self.q[idx]
    def __len__(self): return 4
    def __iter__(self): return iter(self.q)   # also handles tuple unpacking: w,x,y,z = q

    def __mul__(self, other):
        if isinstance(other, Q):
            w1,x1,y1,z1 = self.q
            w2,x2,y2,z2 = other.q
            return Q(array=np.array([
                w1*w2 - x1*x2 - y1*y2 - z1*z2,
                w1*x2 + x1*w2 + y1*z2 - z1*y2,
                w1*y2 - x1*z2 + y1*w2 + z1*x2,
                w1*z2 + x1*y2 - y1*x2 + z1*w2,
            ]))
        if isinstance(other, (int, float)):
            return Q(array=self.q * other)
        return NotImplemented

    def __neg__(self): return Q(array=-self.q)
    def __repr__(self): return f'Q(w={self.w:.4f} x={self.x:.4f} y={self.y:.4f} z={self.z:.4f})'

    # ── rotation ──────────────────────────────────────────────────────────
    def rotate(self, v):
        """Rotate a 3-vector by this quaternion."""
        qv = Q(0.0, *v)
        return (self * qv * self.conjugate).q[1:]

    # ── static methods ────────────────────────────────────────────────────
    @staticmethod
    def slerp(q1, q2, amount):
        dot = np.clip(np.dot(q1.q, q2.q), -1.0, 1.0)
        if dot < 0:                 # take shorter arc
            q2 = -q2
            dot = -dot
        if dot > 0.9995:            # nearly identical — lerp to avoid div/0
            result = q1.q + amount * (q2.q - q1.q)
            return Q(array=result / np.linalg.norm(result))
        theta_0 = np.arccos(dot)
        theta   = theta_0 * amount
        sin_t   = np.sin(theta)
        sin_t0  = np.sin(theta_0)
        s1 = np.cos(theta) - dot * sin_t / sin_t0
        s2 = sin_t / sin_t0
        return Q(array=s1 * q1.q + s2 * q2.q)
    
    @staticmethod
    def from_matrix(R):
        """Construct from 3x3 rotation matrix — Shepperd's method."""
        trace = R[0,0] + R[1,1] + R[2,2]
        if trace > 0:
            s = 0.5 / np.sqrt(trace + 1.0)
            return Q(array=np.array([
                0.25 / s,
                (R[2,1] - R[1,2]) * s,
                (R[0,2] - R[2,0]) * s,
                (R[1,0] - R[0,1]) * s,
            ]))
        elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
            s = 2.0 * np.sqrt(1.0 + R[0,0] - R[1,1] - R[2,2])
            return Q(array=np.array([
                (R[2,1] - R[1,2]) / s,
                0.25 * s,
                (R[0,1] + R[1,0]) / s,
                (R[0,2] + R[2,0]) / s,
            ]))
        elif R[1,1] > R[2,2]:
            s = 2.0 * np.sqrt(1.0 + R[1,1] - R[0,0] - R[2,2])
            return Q(array=np.array([
                (R[0,2] - R[2,0]) / s,
                (R[0,1] + R[1,0]) / s,
                0.25 * s,
                (R[1,2] + R[2,1]) / s,
            ]))
        else:
            s = 2.0 * np.sqrt(1.0 + R[2,2] - R[0,0] - R[1,1])
            return Q(array=np.array([
                (R[1,0] - R[0,1]) / s,
                (R[0,2] + R[2,0]) / s,
                (R[1,2] + R[2,1]) / s,
                0.25 * s,
            ]))