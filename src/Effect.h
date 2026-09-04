// Effect.h

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"

enum class EffectType {
    DAMAGE,
    HEAL,
    BUFF,
    DEBUFF
};

class Effect {
public:
    // Basic constructor
    Effect();

    // Full constructor
    Effect(EffectType type);

private:

};