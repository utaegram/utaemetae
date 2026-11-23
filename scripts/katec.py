"""KATEC(오피넷 좌표) → WGS84 위경도. tmerc lat0=38 lon0=128 k=0.9999 x0=400000 y0=600000, Bessel, towgs84=-146.43,507.89,681.46"""
import math
A, F = 6377397.155, 1/299.1528128
E2 = 2*F - F*F
def _meridian(phi, a=A, e2=E2):
    e4, e6 = e2*e2, e2**3
    return a*((1-e2/4-3*e4/64-5*e6/256)*phi - (3*e2/8+3*e4/32+45*e6/1024)*math.sin(2*phi)
              + (15*e4/256+45*e6/1024)*math.sin(4*phi) - (35*e6/3072)*math.sin(6*phi))
def _tm_inverse(x, y, lat0=38, lon0=128, k0=0.9999, x0=400000, y0=600000):
    e2 = E2; ep2 = e2/(1-e2)
    M = _meridian(math.radians(lat0)) + (y - y0)/k0
    mu = M/(A*(1-e2/4-3*e2**2/64-5*e2**3/256))
    e1 = (1-math.sqrt(1-e2))/(1+math.sqrt(1-e2))
    p1 = mu + (3*e1/2-27*e1**3/32)*math.sin(2*mu) + (21*e1**2/16-55*e1**4/32)*math.sin(4*mu) \
         + (151*e1**3/96)*math.sin(6*mu) + (1097*e1**4/512)*math.sin(8*mu)
    C1 = ep2*math.cos(p1)**2; T1 = math.tan(p1)**2
    N1 = A/math.sqrt(1-e2*math.sin(p1)**2); R1 = A*(1-e2)/(1-e2*math.sin(p1)**2)**1.5
    D = (x - x0)/(N1*k0)
    lat = p1 - (N1*math.tan(p1)/R1)*(D*D/2-(5+3*T1+10*C1-4*C1*C1-9*ep2)*D**4/24
          + (61+90*T1+298*C1+45*T1*T1-252*ep2-3*C1*C1)*D**6/720)
    lon = (D-(1+2*T1+C1)*D**3/6+(5-2*C1+28*T1-3*C1*C1+8*ep2+24*T1*T1)*D**5/120)/math.cos(p1)
    return lat, math.radians(lon0) + lon
def _to_wgs(lat, lon, h=0):
    N = A/math.sqrt(1-E2*math.sin(lat)**2)
    X = (N+h)*math.cos(lat)*math.cos(lon); Y = (N+h)*math.cos(lat)*math.sin(lon); Z = (N*(1-E2)+h)*math.sin(lat)
    X, Y, Z = X-146.43, Y+507.89, Z+681.46
    a, f = 6378137.0, 1/298.257223563; e2 = 2*f-f*f
    lon2 = math.atan2(Y, X); p = math.hypot(X, Y); lat2 = math.atan2(Z, p*(1-e2))
    for _ in range(6):
        N2 = a/math.sqrt(1-e2*math.sin(lat2)**2); lat2 = math.atan2(Z+e2*N2*math.sin(lat2), p)
    return math.degrees(lat2), math.degrees(lon2)
def katec_to_wgs84(x, y):
    return _to_wgs(*_tm_inverse(x, y))
if __name__ == '__main__':
    print(katec_to_wgs84(323070.6, 468751.3))  # 비타민스테이션 쌍용대로 220 ≈ 36.80, 127.13
