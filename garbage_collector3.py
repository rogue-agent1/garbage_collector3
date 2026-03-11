#!/usr/bin/env python3
"""garbage_collector3 - Generational garbage collector (nursery + old gen, write barrier).

Usage: python garbage_collector3.py [--demo]
"""
import sys

class Object:
    _counter = 0
    def __init__(self, name, size=1):
        Object._counter += 1
        self.id = Object._counter
        self.name = name; self.size = size
        self.refs = []  # References to other objects
        self.generation = 0  # 0=nursery, 1=old
        self.age = 0  # Survived collections
        self.marked = False
        self.forwarded = None
    def __repr__(self): return f"{self.name}(gen{self.generation})"

class GenerationalGC:
    PROMOTION_AGE = 2  # Promote after surviving N nursery collections

    def __init__(self, nursery_size=20, old_size=100):
        self.nursery = []  # Young generation
        self.old_gen = []  # Old generation
        self.roots = []
        self.nursery_size = nursery_size
        self.old_size = old_size
        self.remembered_set = set()  # Old objects pointing to young
        self.stats = {"minor_gc": 0, "major_gc": 0, "promoted": 0,
                      "collected_young": 0, "collected_old": 0, "allocated": 0}

    def allocate(self, name, size=1):
        if self._nursery_used() + size > self.nursery_size:
            self.minor_gc()
        obj = Object(name, size)
        self.nursery.append(obj)
        self.stats["allocated"] += 1
        return obj

    def add_root(self, obj):
        self.roots.append(obj)

    def write_barrier(self, src, dst):
        """Called when src.refs includes dst. If old->young, add to remembered set."""
        if src.generation > dst.generation:
            self.remembered_set.add(src.id)

    def set_ref(self, src, dst):
        src.refs.append(dst)
        self.write_barrier(src, dst)

    def _nursery_used(self):
        return sum(o.size for o in self.nursery)

    def minor_gc(self):
        """Collect nursery using copying/Cheney style."""
        self.stats["minor_gc"] += 1
        # Roots: global roots + remembered set (old gen refs to nursery)
        reachable = set()
        def trace(obj):
            if obj.id in reachable: return
            reachable.add(obj.id)
            for ref in obj.refs:
                trace(ref)

        # Trace from roots
        for r in self.roots:
            trace(r)
        # Trace from remembered set
        for obj in self.old_gen:
            if obj.id in self.remembered_set:
                for ref in obj.refs:
                    if ref.generation == 0:
                        trace(ref)

        survivors = []
        collected = 0
        for obj in self.nursery:
            if obj.id in reachable:
                obj.age += 1
                if obj.age >= self.PROMOTION_AGE:
                    obj.generation = 1
                    self.old_gen.append(obj)
                    self.stats["promoted"] += 1
                else:
                    survivors.append(obj)
            else:
                collected += 1
        self.nursery = survivors
        self.stats["collected_young"] += collected
        self.remembered_set.clear()
        # Rebuild remembered set
        for obj in self.old_gen:
            for ref in obj.refs:
                if ref.generation == 0:
                    self.remembered_set.add(obj.id)
                    break

    def major_gc(self):
        """Full mark-sweep of old generation."""
        self.stats["major_gc"] += 1
        reachable = set()
        def trace(obj):
            if obj.id in reachable: return
            reachable.add(obj.id)
            for ref in obj.refs:
                trace(ref)
        for r in self.roots:
            trace(r)
        before = len(self.old_gen)
        self.old_gen = [o for o in self.old_gen if o.id in reachable]
        self.stats["collected_old"] += before - len(self.old_gen)
        # Also clean nursery
        self.nursery = [o for o in self.nursery if o.id in reachable]

    def info(self):
        return {
            "nursery": f"{len(self.nursery)} objs ({self._nursery_used()}/{self.nursery_size})",
            "old_gen": f"{len(self.old_gen)} objs",
            "remembered": len(self.remembered_set),
            **self.stats,
        }

def main():
    print("=== Generational Garbage Collector ===\n")
    gc = GenerationalGC(nursery_size=10)

    # Create a root object
    root = gc.allocate("root")
    gc.add_root(root)

    # Allocate objects, some referenced, some garbage
    a = gc.allocate("A"); gc.set_ref(root, a)
    b = gc.allocate("B"); gc.set_ref(a, b)
    gc.allocate("garbage1")  # No refs
    gc.allocate("garbage2")  # No refs
    print(f"After initial alloc: {gc.info()}")

    # Trigger minor GC by filling nursery
    print(f"\nAllocating to trigger minor GC:")
    for i in range(8):
        gc.allocate(f"temp{i}")
    print(f"After fills: {gc.info()}")

    # More allocation cycles to promote objects
    print(f"\nMultiple cycles (promoting survivors):")
    for cycle in range(3):
        c = gc.allocate(f"cycle{cycle}")
        gc.set_ref(root, c)
        for j in range(10):
            gc.allocate(f"junk{cycle}_{j}")
        print(f"  Cycle {cycle}: {gc.info()}")

    # Major GC
    print(f"\nMajor GC:")
    gc.major_gc()
    print(f"  After: {gc.info()}")

    # Show what survived
    print(f"\nOld gen objects:")
    for obj in gc.old_gen:
        print(f"  {obj} (age={obj.age}, refs={[str(r) for r in obj.refs]})")

if __name__ == "__main__":
    main()
