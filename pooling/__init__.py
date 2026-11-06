"""Object Pooling package for zero-allocation performance."""
from pooling.object_pool import ObjectPool
from pooling.particle_pool import ParticlePool, PooledParticle
from pooling.damage_number_pool import (
    DamageNumberPool,
    PooledDamageNumber,
    get_cached_damage_surfaces,
)
from pooling.projectile_pool import ProjectilePool, PooledProjectile

__all__ = [
    "ObjectPool",
    "ParticlePool",
    "PooledParticle",
    "DamageNumberPool",
    "PooledDamageNumber",
    "get_cached_damage_surfaces",
    "ProjectilePool",
    "PooledProjectile",
]

