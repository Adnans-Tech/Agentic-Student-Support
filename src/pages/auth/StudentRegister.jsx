/**
 * Redesigned Register Page — Dark Figma Theme
 * Handles both Student and Faculty registration with role toggle.
 * Matches the login page design with DotGrid background and scrollable card.
 */

import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import authService from '../../services/authService';
import { validators, formatBackendError } from '../../utils/validators';
import { pageTransition } from '../../animations/variants';
import Toast from '../../components/common/Toast';
import DotGrid from '../../components/animations/DotGrid';
import styles from './Auth.module.css';

const DEPARTMENTS = ['CSM', 'CSE', 'CSD', 'CSO', 'ECE', 'EEE', 'IT', 'CIVIL', 'MECH'];
const SECTIONS = ['A', 'B', 'C'];
const YEARS = [1, 2, 3, 4];

const Register = () => {
    const navigate = useNavigate();

    const [role, setRole] = useState('student');

    // Student fields
    const [studentData, setStudentData] = useState({
        full_name: '',
        roll_number: '',
        email: '',
        password: '',
        confirm_password: '',
        department: '',
        year: '',
        section: '',
    });

    // Faculty fields
    const [facultyData, setFacultyData] = useState({
        full_name: '',
        employee_id: '',
        email: '',
        password: '',
        confirm_password: '',
        department: '',
        designation: '',
        subject_incharge: '',
        class_incharge: '',
    });

    const [errors, setErrors] = useState({});
    const [loading, setLoading] = useState(false);
    const [toast, setToast] = useState({ show: false, message: '', type: 'error' });
    const [passwordStrength, setPasswordStrength] = useState({ strength: '', score: 0, className: '' });

    const formData = role === 'student' ? studentData : facultyData;
    const setFormData = role === 'student' ? setStudentData : setFacultyData;

    const handleChange = (e) => {
        const { name, value } = e.target;

        // Auto-uppercase specific fields
        const uppercaseFields = ['full_name', 'roll_number', 'department', 'section', 'employee_id', 'class_incharge'];
        const processedValue = uppercaseFields.includes(name) ? value.toUpperCase() : value;

        setFormData(prev => ({ ...prev, [name]: processedValue }));

        // Password strength check
        if (name === 'password') {
            setPasswordStrength(validators.passwordStrength(processedValue));
        }

        // Clear error
        if (errors[name]) {
            setErrors(prev => ({ ...prev, [name]: null }));
        }
        setToast({ show: false, message: '', type: 'error' });
    };

    const validate = () => {
        const newErrors = {};

        if (role === 'student') {
            newErrors.full_name = validators.required(studentData.full_name, 'Full name');
            newErrors.roll_number = validators.rollNumber(studentData.roll_number);
            newErrors.email = validators.email(studentData.email);
            newErrors.password = validators.password(studentData.password);
            newErrors.confirm_password = validators.confirmPassword(studentData.password, studentData.confirm_password);
            newErrors.department = validators.required(studentData.department, 'Department');
            newErrors.year = !studentData.year ? 'Year is required' : null;
            newErrors.section = validators.required(studentData.section, 'Section');
        } else {
            newErrors.full_name = validators.required(facultyData.full_name, 'Full name');
            newErrors.email = validators.email(facultyData.email);
            newErrors.password = validators.password(facultyData.password);
            newErrors.confirm_password = validators.confirmPassword(facultyData.password, facultyData.confirm_password);
            newErrors.department = validators.required(facultyData.department, 'Department');
        }

        setErrors(newErrors);
        return !Object.values(newErrors).some(error => error !== null);
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setToast({ show: false, message: '', type: 'error' });

        if (!validate()) return;

        setLoading(true);

        try {
            const payload = {
                ...formData,
                role,
            };

            const response = await authService.register(payload);

            if (response.success) {
                navigate('/verify-otp', { state: { email: formData.email, role } });
            } else {
                setToast({
                    show: true,
                    message: formatBackendError(response),
                    type: 'error'
                });
            }
        } catch (error) {
            setToast({
                show: true,
                message: formatBackendError(error),
                type: 'error'
            });
        } finally {
            setLoading(false);
        }
    };

    const handleRoleChange = (newRole) => {
        setRole(newRole);
        setErrors({});
        setToast({ show: false, message: '', type: 'error' });
    };

    return (
        <div className={styles.authContainer}>
            {/* Interactive DotGrid background */}
            <div className={styles.dotGridBackground}>
                <DotGrid
                    dotSize={6}
                    gap={15}
                    baseColor="#0a0119"
                    activeColor="#f4f2fd"
                    proximity={120}
                    shockRadius={280}
                    shockStrength={9}
                    resistance={750}
                    returnDuration={1.5}
                />
            </div>

            <Toast
                message={toast.message}
                type={toast.type}
                show={toast.show}
                onClose={() => setToast({ show: false, message: '', type: 'error' })}
            />

            {/* Header — outside the card */}
            <div className={styles.authWrapper}>
                <div className={styles.logoSection}>
                    <h1 className={styles.title}>ACE ASSIST</h1>
                    <p className={styles.subtitle}>Create Your Account</p>
                    <p className={styles.tagline}>Join the Intelligent Campus Community</p>
                </div>

            <motion.div
                className={styles.authCardScrollable}
                {...pageTransition}
                style={{ maxWidth: '540px' }}
            >

                {/* Role Toggle */}
                <div className={styles.roleToggle}>
                    <button
                        type="button"
                        className={`${styles.roleButton} ${role === 'student' ? styles.roleActive : ''}`}
                        onClick={() => handleRoleChange('student')}
                    >
                        🎓 Student
                    </button>
                    <button
                        type="button"
                        className={`${styles.roleButton} ${role === 'faculty' ? styles.roleActive : ''}`}
                        onClick={() => handleRoleChange('faculty')}
                    >
                        📋 Faculty
                    </button>
                </div>

                {/* Registration Form */}
                <form onSubmit={handleSubmit} className={styles.form}>

                    {role === 'student' ? (
                        <>
                            {/* Student: Full Name & Roll Number */}
                            <div className={styles.formGrid}>
                                <div className={styles.formGroup}>
                                    <label htmlFor="full_name" className={styles.label}>Full Name</label>
                                    <input
                                        type="text"
                                        id="full_name"
                                        name="full_name"
                                        value={studentData.full_name}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.full_name ? styles.inputError : ''}`}
                                        placeholder="JOHN DOE"
                                        disabled={loading}
                                    />
                                    {errors.full_name && <span className={styles.errorText}>{errors.full_name}</span>}
                                </div>

                                <div className={styles.formGroup}>
                                    <label htmlFor="roll_number" className={styles.label}>Roll Number</label>
                                    <input
                                        type="text"
                                        id="roll_number"
                                        name="roll_number"
                                        value={studentData.roll_number}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.roll_number ? styles.inputError : ''}`}
                                        placeholder="22AG1A6601"
                                        disabled={loading}
                                        maxLength={10}
                                    />
                                    {errors.roll_number && <span className={styles.errorText}>{errors.roll_number}</span>}
                                </div>
                            </div>

                            {/* Student: Email */}
                            <div className={styles.formGroup}>
                                <label htmlFor="email" className={styles.label}>Email</label>
                                <input
                                    type="email"
                                    id="email"
                                    name="email"
                                    value={studentData.email}
                                    onChange={handleChange}
                                    className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                                    placeholder="your.email@example.com"
                                    disabled={loading}
                                />
                                {errors.email && <span className={styles.errorText}>{errors.email}</span>}
                            </div>

                            {/* Student: Department, Year, Section */}
                            <div className={styles.formGrid} style={{ gridTemplateColumns: '1fr 1fr 1fr' }}>
                                <div className={styles.formGroup}>
                                    <label htmlFor="student_department" className={styles.label}>Department</label>
                                    <select
                                        id="student_department"
                                        name="department"
                                        value={studentData.department}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.department ? styles.inputError : ''}`}
                                        disabled={loading}
                                    >
                                        <option value="">Select</option>
                                        {DEPARTMENTS.map(dep => (
                                            <option key={dep} value={dep}>{dep}</option>
                                        ))}
                                    </select>
                                    {errors.department && <span className={styles.errorText}>{errors.department}</span>}
                                </div>

                                <div className={styles.formGroup}>
                                    <label htmlFor="student_year" className={styles.label}>Year</label>
                                    <select
                                        id="student_year"
                                        name="year"
                                        value={studentData.year}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.year ? styles.inputError : ''}`}
                                        disabled={loading}
                                    >
                                        <option value="">Select</option>
                                        {YEARS.map(y => (
                                            <option key={y} value={y}>{y}</option>
                                        ))}
                                    </select>
                                    {errors.year && <span className={styles.errorText}>{errors.year}</span>}
                                </div>

                                <div className={styles.formGroup}>
                                    <label htmlFor="student_section" className={styles.label}>Section</label>
                                    <select
                                        id="student_section"
                                        name="section"
                                        value={studentData.section}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.section ? styles.inputError : ''}`}
                                        disabled={loading}
                                    >
                                        <option value="">Select</option>
                                        {SECTIONS.map(sec => (
                                            <option key={sec} value={sec}>{sec}</option>
                                        ))}
                                    </select>
                                    {errors.section && <span className={styles.errorText}>{errors.section}</span>}
                                </div>
                            </div>
                        </>
                    ) : (
                        <>
                            {/* Faculty: Full Name & Employee ID */}
                            <div className={styles.formGrid}>
                                <div className={styles.formGroup}>
                                    <label htmlFor="full_name" className={styles.label}>Full Name</label>
                                    <input
                                        type="text"
                                        id="full_name"
                                        name="full_name"
                                        value={facultyData.full_name}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.full_name ? styles.inputError : ''}`}
                                        placeholder="DR. JOHN DOE"
                                        disabled={loading}
                                    />
                                    {errors.full_name && <span className={styles.errorText}>{errors.full_name}</span>}
                                </div>

                                <div className={styles.formGroup}>
                                    <label htmlFor="employee_id" className={styles.label}>Employee ID (Optional)</label>
                                    <input
                                        type="text"
                                        id="employee_id"
                                        name="employee_id"
                                        value={facultyData.employee_id}
                                        onChange={handleChange}
                                        className={styles.input}
                                        placeholder="FAC12345"
                                        disabled={loading}
                                    />
                                </div>
                            </div>

                            {/* Faculty: Email */}
                            <div className={styles.formGroup}>
                                <label htmlFor="email" className={styles.label}>Official Email</label>
                                <input
                                    type="email"
                                    id="email"
                                    name="email"
                                    value={facultyData.email}
                                    onChange={handleChange}
                                    className={`${styles.input} ${errors.email ? styles.inputError : ''}`}
                                    placeholder="you@aceec.ac.in"
                                    disabled={loading}
                                />
                                {errors.email && <span className={styles.errorText}>{errors.email}</span>}
                            </div>

                            {/* Faculty: Department & Designation */}
                            <div className={styles.formGrid}>
                                <div className={styles.formGroup}>
                                    <label htmlFor="department" className={styles.label}>Department</label>
                                    <select
                                        id="department"
                                        name="department"
                                        value={facultyData.department}
                                        onChange={handleChange}
                                        className={`${styles.input} ${errors.department ? styles.inputError : ''}`}
                                        disabled={loading}
                                    >
                                        <option value="">Select</option>
                                        {DEPARTMENTS.map(dep => (
                                            <option key={dep} value={dep}>{dep}</option>
                                        ))}
                                    </select>
                                    {errors.department && <span className={styles.errorText}>{errors.department}</span>}
                                </div>

                                <div className={styles.formGroup}>
                                    <label htmlFor="designation" className={styles.label}>Designation</label>
                                    <input
                                        type="text"
                                        id="designation"
                                        name="designation"
                                        value={facultyData.designation}
                                        onChange={handleChange}
                                        className={styles.input}
                                        placeholder="Professor"
                                        disabled={loading}
                                    />
                                </div>
                            </div>

                            {/* Faculty: Subject & Class In-Charge */}
                            <div className={styles.formGrid}>
                                <div className={styles.formGroup}>
                                    <label htmlFor="subject_incharge" className={styles.label}>Subject In-Charge</label>
                                    <input
                                        type="text"
                                        id="subject_incharge"
                                        name="subject_incharge"
                                        value={facultyData.subject_incharge}
                                        onChange={handleChange}
                                        className={styles.input}
                                        placeholder="Data Structures"
                                        disabled={loading}
                                    />
                                </div>

                                <div className={styles.formGroup}>
                                    <label htmlFor="class_incharge" className={styles.label}>Class In-Charge (Optional)</label>
                                    <input
                                        type="text"
                                        id="class_incharge"
                                        name="class_incharge"
                                        value={facultyData.class_incharge}
                                        onChange={handleChange}
                                        className={styles.input}
                                        placeholder="CSM-A"
                                        disabled={loading}
                                    />
                                </div>
                            </div>
                        </>
                    )}

                    {/* Password (both roles) */}
                    <div className={styles.formGroup}>
                        <label htmlFor="password" className={styles.label}>Password</label>
                        <input
                            type="password"
                            id="password"
                            name="password"
                            value={formData.password}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.password ? styles.inputError : ''}`}
                            placeholder="Min 8 chars, uppercase, digit, special (_.!-)"
                            disabled={loading}
                        />
                        {errors.password && <span className={styles.errorText}>{errors.password}</span>}

                        {/* Password Strength */}
                        {formData.password && (
                            <div className={styles.passwordStrength}>
                                <div className={styles.strengthBar}>
                                    <div className={`${styles.strengthFill} ${styles[passwordStrength.className]}`} />
                                </div>
                                <span className={`${styles.strengthLabel} ${styles[passwordStrength.className]}`}>
                                    {passwordStrength.strength}
                                </span>
                            </div>
                        )}
                    </div>

                    {/* Confirm Password */}
                    <div className={styles.formGroup}>
                        <label htmlFor="confirm_password" className={styles.label}>Confirm Password</label>
                        <input
                            type="password"
                            id="confirm_password"
                            name="confirm_password"
                            value={formData.confirm_password}
                            onChange={handleChange}
                            className={`${styles.input} ${errors.confirm_password ? styles.inputError : ''}`}
                            placeholder="••••••••"
                            disabled={loading}
                        />
                        {errors.confirm_password && <span className={styles.errorText}>{errors.confirm_password}</span>}
                    </div>

                    {/* Submit */}
                    <motion.button
                        type="submit"
                        className={styles.submitButton}
                        disabled={loading}
                        whileHover={{ scale: loading ? 1 : 1.02 }}
                        whileTap={{ scale: loading ? 1 : 0.98 }}
                    >
                        {loading ? 'Creating Account...' : 'Create Account'}
                        {!loading && <span className={styles.submitArrow}>→</span>}
                    </motion.button>
                </form>

                {/* Links */}
                <div className={styles.links}>
                    <p className={styles.linkText}>
                        Already have an account?{' '}
                        <Link to="/login" className={styles.link}>
                            Login
                        </Link>
                    </p>
                </div>
            </motion.div>
            </div>
        </div>
    );
};

export default Register;
