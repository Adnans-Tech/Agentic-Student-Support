/**
 * Framer Motion Animation Variants
 * Professional, subtle animations for ACE College Support System
 */

// === PAGE TRANSITIONS ===

export const pageTransition = {
    initial: {
        opacity: 0,
        y: 10
    },
    animate: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.25,
            ease: 'easeInOut'
        }
    },
    exit: {
        opacity: 0,
        y: -10,
        transition: {
            duration: 0.2,
            ease: 'easeInOut'
        }
    }
};

// === CARD ANIMATIONS ===

export const cardVariants = {
    hidden: {
        opacity: 0,
        y: 10
    },
    visible: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.2,
            ease: 'easeOut'
        }
    }
};

export const cardHover = {
    scale: 1.02,
    boxShadow: '0 8px 24px rgba(0, 0, 0, 0.5)',
    transition: {
        duration: 0.2,
        ease: 'easeOut'
    }
};

export const cardTap = {
    scale: 0.98,
    transition: {
        duration: 0.1
    }
};

// === BUTTON ANIMATIONS ===

export const buttonHover = {
    scale: 1.02,
    transition: {
        duration: 0.15,
        ease: 'easeOut'
    }
};

export const buttonTap = {
    scale: 0.96,
    transition: {
        duration: 0.1
    }
};

// === STAGGER ANIMATIONS ===

export const staggerContainer = {
    hidden: {
        opacity: 0
    },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.05,
            delayChildren: 0.1
        }
    }
};

export const staggerItem = {
    hidden: {
        opacity: 0,
        y: 10
    },
    visible: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.2,
            ease: 'easeOut'
        }
    }
};

// === MODAL ANIMATIONS ===

export const modalBackdrop = {
    hidden: {
        opacity: 0
    },
    visible: {
        opacity: 1,
        transition: {
            duration: 0.2
        }
    },
    exit: {
        opacity: 0,
        transition: {
            duration: 0.15
        }
    }
};

export const modalContent = {
    hidden: {
        opacity: 0,
        scale: 0.95,
        y: 20
    },
    visible: {
        opacity: 1,
        scale: 1,
        y: 0,
        transition: {
            duration: 0.25,
            ease: 'easeOut'
        }
    },
    exit: {
        opacity: 0,
        scale: 0.95,
        y: 20,
        transition: {
            duration: 0.2
        }
    }
};

// === OTP INPUT ANIMATIONS ===

export const otpStagger = {
    hidden: {
        opacity: 0
    },
    visible: {
        opacity: 1,
        transition: {
            staggerChildren: 0.08
        }
    }
};

export const otpDigit = {
    hidden: {
        opacity: 0,
        scale: 0.8
    },
    visible: {
        opacity: 1,
        scale: 1,
        transition: {
            duration: 0.2,
            type: 'spring',
            stiffness: 300,
            damping: 20
        }
    }
};

// === FADE ANIMATIONS ===

export const fadeIn = {
    hidden: {
        opacity: 0
    },
    visible: {
        opacity: 1,
        transition: {
            duration: 0.2
        }
    }
};

export const fadeInUp = {
    hidden: {
        opacity: 0,
        y: 20
    },
    visible: {
        opacity: 1,
        y: 0,
        transition: {
            duration: 0.25,
            ease: 'easeOut'
        }
    }
};

// === SLIDE ANIMATIONS ===

export const slideInRight = {
    hidden: {
        opacity: 0,
        x: 20
    },
    visible: {
        opacity: 1,
        x: 0,
        transition: {
            duration: 0.25,
            ease: 'easeOut'
        }
    }
};

export const slideInLeft = {
    hidden: {
        opacity: 0,
        x: -20
    },
    visible: {
        opacity: 1,
        x: 0,
        transition: {
            duration: 0.25,
            ease: 'easeOut'
        }
    }
};

// === NAVBAR/SIDEBAR ANIMATIONS ===

export const navItemHover = {
    scale: 1.05,
    x: 4,
    transition: {
        duration: 0.15
    }
};

export const dropdownVariants = {
    hidden: {
        opacity: 0,
        y: -10,
        scale: 0.95
    },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: {
            duration: 0.2,
            ease: 'easeOut'
        }
    },
    exit: {
        opacity: 0,
        y: -10,
        scale: 0.95,
        transition: {
            duration: 0.15
        }
    }
};

// === TOAST/NOTIFICATION ANIMATIONS ===

export const toastVariants = {
    hidden: {
        opacity: 0,
        y: -20,
        scale: 0.9
    },
    visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: {
            duration: 0.25,
            ease: 'easeOut'
        }
    },
    exit: {
        opacity: 0,
        scale: 0.9,
        transition: {
            duration: 0.2
        }
    }
};

// === LOADING ANIMATIONS ===

export const spinnerVariants = {
    animate: {
        rotate: 360,
        transition: {
            duration: 1,
            repeat: Infinity,
            ease: 'linear'
        }
    }
};

export const pulseVariants = {
    animate: {
        scale: [1, 1.1, 1],
        opacity: [1, 0.8, 1],
        transition: {
            duration: 1.5,
            repeat: Infinity,
            ease: 'easeInOut'
        }
    }
};

// === HELPER: Check if user prefers reduced motion ===

export const shouldReduceMotion = () => {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
};

// === HELPER: Get transition config based on user preference ===

export const getTransition = (duration = 0.2, ease = 'easeOut') => {
    if (shouldReduceMotion()) {
        return { duration: 0.01 };
    }
    return { duration, ease };
};
